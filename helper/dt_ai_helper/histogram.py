"""Histogram statistics + deterministic issue tags from an exported preview.

Plan §6 / Phase 3: compute per-channel and luma statistics from the
exported preview JPEG (Pillow + numpy), then run a deterministic rule
layer over those statistics (plus EXIF and the resolved edit state) that
produces a list of ``issue_tags``. The tags -- not the raw numbers -- are
what feeds the Optimize retrieval query (``prompts.optimize_retrieval_query``)
and give the LLM's output stable structure across models (plan §5.5/§6).

**The preview is a display-referred sRGB JPEG**, not scene-referred sensor
data -- every stat below is a display-referred *approximation* of the
underlying image (post whatever tone-mapping/JPEG-encoding already
happened during export). Treat percentiles, clipping percentages, and the
white-balance/saturation hints as directional signals for prompting an
LLM, not as scene-linear photometric measurements.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

#: A pixel channel value is "clipped" if it falls within this fraction of
#: full-scale (plan §6: "within 1% of black/white").
CLIP_FRACTION = 0.01
_CLIP_LOW = 255 * CLIP_FRACTION
_CLIP_HIGH = 255 - _CLIP_LOW

#: Luma percentiles reported (plan §6).
PERCENTILES = (1, 5, 50, 95, 99)

# ---------------------------------------------------------------------------
# Histogram + stats
# ---------------------------------------------------------------------------


def _load_rgb_array(image_path: str | Path) -> np.ndarray:
    """Load ``image_path`` as an ``(H, W, 3)`` uint8 RGB array."""
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        return np.asarray(rgb, dtype=np.uint8)


def _histogram_256(channel: np.ndarray) -> list[int]:
    hist, _ = np.histogram(channel, bins=256, range=(0, 256))
    return hist.tolist()


def _clipped_pct(channel: np.ndarray) -> dict[str, float]:
    total = channel.size
    black = float(np.count_nonzero(channel <= _CLIP_LOW)) / total * 100.0
    white = float(np.count_nonzero(channel >= _CLIP_HIGH)) / total * 100.0
    return {"black_pct": black, "white_pct": white}


def _percentiles(channel: np.ndarray) -> dict[str, float]:
    values = np.percentile(channel, PERCENTILES)
    return {f"p{p}": float(v) for p, v in zip(PERCENTILES, values, strict=True)}


def _luma(rgb: np.ndarray) -> np.ndarray:
    """Rec. 601 luma -- matches what most preview histograms use."""
    r = rgb[..., 0].astype(np.float64)
    g = rgb[..., 1].astype(np.float64)
    b = rgb[..., 2].astype(np.float64)
    return 0.299 * r + 0.587 * g + 0.114 * b


def _mean_hsv_saturation(rgb: np.ndarray) -> float:
    """Mean HSV saturation, 0-100 scale, computed without a colour library."""
    arr = rgb.astype(np.float64) / 255.0
    cmax = arr.max(axis=-1)
    cmin = arr.min(axis=-1)
    delta = cmax - cmin
    sat = np.divide(delta, cmax, out=np.zeros_like(delta), where=cmax > 0)
    return float(sat.mean() * 100.0)


def _dynamic_range_utilization(luma: np.ndarray) -> float:
    """0-100 score: how much of the 0-255 luma range the image actually uses.

    Simple heuristic: the p1-p99 luma spread as a fraction of full scale.
    A well-exposed, contrasty image uses most of the range; a flat/foggy
    one uses little of it.
    """
    p1, p99 = np.percentile(luma, [1, 99])
    return float(np.clip((p99 - p1) / 255.0 * 100.0, 0.0, 100.0))


def _gray_world_wb_hint(rgb: np.ndarray) -> dict[str, float]:
    """Gray-world white-balance hint: per-channel mean ratios to green.

    Gray-world assumes the scene averages to neutral gray; if the R/G or
    B/G ratio strays far from 1.0 there's likely a color cast (or the
    image genuinely isn't gray-world-neutral, e.g. a sunset -- this is a
    hint for the LLM, not a verdict).
    """
    means = rgb.reshape(-1, 3).mean(axis=0)
    r_mean, g_mean, b_mean = (float(m) for m in means)
    g_safe = g_mean if g_mean > 1e-6 else 1e-6
    return {
        "r_mean": r_mean,
        "g_mean": g_mean,
        "b_mean": b_mean,
        "r_g_ratio": r_mean / g_safe,
        "b_g_ratio": b_mean / g_safe,
    }


def _noise_proxy(luma: np.ndarray) -> float:
    """High-frequency stddev in the shadow region, as an ISO-noise proxy.

    Takes pixels below the 25th luma percentile ("shadows"), high-pass
    filters them with a simple 3x3 Laplacian-like kernel (difference from a
    local mean), and reports the stddev of the residual. Real noise
    estimation would need the raw sensor data; this is a cheap, offline,
    JPEG-preview-only proxy intended to correlate with (not precisely
    measure) high-ISO grain -- correlated with EXIF ISO by the rule layer,
    not a substitute for it.
    """
    if luma.size < 9:
        return 0.0
    threshold = np.percentile(luma, 25)
    mask = luma <= threshold
    if not mask.any():
        return 0.0

    # 3x3 box-blur via array slicing (no scipy dependency).
    padded = np.pad(luma, 1, mode="edge")
    blurred = np.zeros_like(luma)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            blurred += padded[dy : dy + luma.shape[0], dx : dx + luma.shape[1]]
    blurred /= 9.0

    residual = luma - blurred
    shadow_residual = residual[mask]
    return float(shadow_residual.std())


def compute_stats(image_path: str | Path) -> dict[str, Any]:
    """Compute histogram + derived statistics from an exported preview JPEG.

    Returns the ``histogram`` sub-object of plan §5.2's ``image_context``
    shape, plus a few extra fields (``mean_saturation``,
    ``dynamic_range_score``, ``wb_hint``, ``noise_proxy``) consumed by
    :func:`derive_issue_tags` and surfaced to the LLM as raw context.
    """
    rgb = _load_rgb_array(image_path)
    luma = _luma(rgb)

    per_channel: dict[str, Any] = {}
    for idx, name in enumerate(("r", "g", "b")):
        channel = rgb[..., idx]
        per_channel[name] = {
            "histogram": _histogram_256(channel),
            "mean": float(channel.mean()),
            **_clipped_pct(channel),
            **_percentiles(channel),
        }

    luma_u8 = np.clip(luma, 0, 255).astype(np.uint8)
    luma_stats = {
        "histogram": _histogram_256(luma_u8),
        "mean": float(luma.mean()),
        **_clipped_pct(luma),
        **_percentiles(luma),
    }

    return {
        "width": int(rgb.shape[1]),
        "height": int(rgb.shape[0]),
        "per_channel": per_channel,
        "luma": luma_stats,
        "clipped_black_pct": luma_stats["black_pct"],
        "clipped_white_pct": luma_stats["white_pct"],
        "luma_percentiles": {k: v for k, v in luma_stats.items() if k.startswith("p")},
        "mean_saturation": _mean_hsv_saturation(rgb),
        "dynamic_range_score": _dynamic_range_utilization(luma),
        "wb_hint": _gray_world_wb_hint(rgb),
        "noise_proxy": _noise_proxy(luma),
    }


# ---------------------------------------------------------------------------
# Rule layer -> deterministic issue tags (plan §6)
# ---------------------------------------------------------------------------

#: Thresholds tuned against the synthetic fixtures in test_histogram.py --
#: these are heuristics for prompting an LLM, not photometric ground truth.
UNDEREXPOSED_MEAN_LUMA = 60.0
OVEREXPOSED_MEAN_LUMA = 200.0
CLIPPED_PCT_THRESHOLD = 1.0
LOW_CONTRAST_RANGE_SCORE = 25.0
FLAT_MIDTONES_IQR = 40.0
COLOR_CAST_RATIO_THRESHOLD = 1.15
LOW_SATURATION_THRESHOLD = 8.0
HIGH_ISO_THRESHOLD = 1600
HIGH_ISO_NOISE_PROXY_THRESHOLD = 4.0
LONG_EXPOSURE_SECONDS = 1.0
ULTRA_WIDE_FOCAL_LENGTH_MM = 20.0


def _enabled_ops(enabled_modules: list[dict[str, Any]] | None) -> set[str]:
    return {m.get("op", "") for m in (enabled_modules or [])}


def derive_issue_tags(
    stats: dict[str, Any],
    *,
    exif: dict[str, Any] | None = None,
    enabled_modules: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Deterministic issue tags from histogram stats + EXIF + edit state.

    Order is meaningful only insofar as it's stable and deduplicated; the
    LLM and the retrieval query both just want the set. Kept intentionally
    conservative (few thresholds, each independently testable) rather than
    a single opaque score, per plan §6's "deterministic tags make output
    stable across models" rationale.
    """
    exif = exif or {}
    tags: list[str] = []

    luma = stats.get("luma", {})
    mean_luma = luma.get("mean", 128.0)
    p5 = luma.get("p5", 0.0)
    p95 = luma.get("p95", 255.0)
    black_pct = stats.get("clipped_black_pct", luma.get("black_pct", 0.0))
    white_pct = stats.get("clipped_white_pct", luma.get("white_pct", 0.0))

    if mean_luma < UNDEREXPOSED_MEAN_LUMA:
        tags.append("underexposed")
    if mean_luma > OVEREXPOSED_MEAN_LUMA:
        tags.append("overexposed")
    if white_pct > CLIPPED_PCT_THRESHOLD:
        tags.append("highlights_clipped")
    if black_pct > CLIPPED_PCT_THRESHOLD:
        tags.append("shadows_clipped")

    dynamic_range_score = stats.get("dynamic_range_score", 100.0)
    if dynamic_range_score < LOW_CONTRAST_RANGE_SCORE:
        tags.append("low_contrast")
    if (p95 - p5) < FLAT_MIDTONES_IQR:
        tags.append("flat_midtones")

    wb_hint = stats.get("wb_hint", {})
    r_g = wb_hint.get("r_g_ratio", 1.0)
    b_g = wb_hint.get("b_g_ratio", 1.0)
    if r_g >= COLOR_CAST_RATIO_THRESHOLD and r_g >= b_g:
        tags.append("color_cast_red")
    elif b_g >= COLOR_CAST_RATIO_THRESHOLD and b_g > r_g:
        tags.append("color_cast_blue")
    elif r_g <= 1.0 / COLOR_CAST_RATIO_THRESHOLD and r_g <= b_g:
        tags.append("color_cast_cyan")
    elif b_g <= 1.0 / COLOR_CAST_RATIO_THRESHOLD:
        tags.append("color_cast_yellow")

    mean_saturation = stats.get("mean_saturation", 50.0)
    if mean_saturation < LOW_SATURATION_THRESHOLD:
        tags.append("low_saturation")

    iso = exif.get("iso")
    noise_proxy = stats.get("noise_proxy", 0.0)
    is_high_iso = iso is not None and iso >= HIGH_ISO_THRESHOLD
    if is_high_iso and noise_proxy >= HIGH_ISO_NOISE_PROXY_THRESHOLD:
        tags.append("high_iso_noise")

    ops = _enabled_ops(enabled_modules)
    sharpen_ops = {"sharpen", "diffuse"}
    denoise_ops = {"denoiseprofile", "rawdenoise", "nlmeans"}
    if "high_iso_noise" in tags or is_high_iso:
        if not (ops & denoise_ops):
            tags.append("no_denoise_enabled")
    if ("low_contrast" in tags or "flat_midtones" in tags) and not (ops & sharpen_ops):
        tags.append("no_sharpening_enabled")

    exposure_seconds = exif.get("exposure")
    if exposure_seconds is not None and exposure_seconds >= LONG_EXPOSURE_SECONDS:
        tags.append("long_exposure_hot_pixels_check")

    focal_length = exif.get("focal_length")
    if focal_length is not None and focal_length <= ULTRA_WIDE_FOCAL_LENGTH_MM:
        if "lens" not in ops:
            tags.append("ultra_wide_lens_correction_check")

    # De-dupe while preserving first-seen order (tags above never repeat,
    # but keep this robust if the rule set grows).
    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    return deduped


def analyze(
    image_path: str | Path,
    *,
    exif: dict[str, Any] | None = None,
    enabled_modules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Convenience wrapper: :func:`compute_stats` + :func:`derive_issue_tags`."""
    stats = compute_stats(image_path)
    tags = derive_issue_tags(stats, exif=exif, enabled_modules=enabled_modules)
    return {"stats": stats, "issue_tags": tags}
