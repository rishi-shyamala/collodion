"""Offline tests for histogram.py (plan §6, W6 scope).

Synthetic images built in-memory with Pillow/numpy -- no fixture files, no
network. Each covers one rule-layer tag family: pure black (underexposed +
shadows clipped), a clipped-white "sky" (overexposed + highlights clipped),
a blue color cast, and a flat low-contrast gray card.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from dt_ai_helper import histogram
from PIL import Image


def _save(tmp_path: Path, name: str, arr: np.ndarray) -> Path:
    path = tmp_path / name
    Image.fromarray(arr, mode="RGB").save(path, format="JPEG", quality=95)
    return path


@pytest.fixture()
def tmp_images(tmp_path: Path):
    return tmp_path


# ---------------------------------------------------------------------------
# Pure black -> underexposed + shadows_clipped
# ---------------------------------------------------------------------------


def test_pure_black_image(tmp_images):
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    path = _save(tmp_images, "black.jpg", arr)

    result = histogram.analyze(path)
    stats = result["stats"]
    tags = result["issue_tags"]

    assert stats["luma"]["mean"] < 5.0
    assert stats["clipped_black_pct"] > 90.0
    assert "underexposed" in tags
    assert "shadows_clipped" in tags
    assert "overexposed" not in tags


# ---------------------------------------------------------------------------
# Clipped white "sky" -> overexposed + highlights_clipped
# ---------------------------------------------------------------------------


def test_clipped_white_sky(tmp_images):
    arr = np.full((64, 64, 3), 255, dtype=np.uint8)
    path = _save(tmp_images, "sky.jpg", arr)

    result = histogram.analyze(path)
    stats = result["stats"]
    tags = result["issue_tags"]

    assert stats["luma"]["mean"] > 250.0
    assert stats["clipped_white_pct"] > 90.0
    assert "overexposed" in tags
    assert "highlights_clipped" in tags
    assert "underexposed" not in tags


# ---------------------------------------------------------------------------
# Blue color cast (gray card pushed heavily toward blue)
# ---------------------------------------------------------------------------


def test_blue_color_cast(tmp_images):
    arr = np.empty((64, 64, 3), dtype=np.uint8)
    arr[..., 0] = 90  # R
    arr[..., 1] = 90  # G
    arr[..., 2] = 190  # B, well above the cast threshold vs. green
    path = _save(tmp_images, "blue_cast.jpg", arr)

    result = histogram.analyze(path)
    stats = result["stats"]
    tags = result["issue_tags"]

    assert stats["wb_hint"]["b_g_ratio"] > 1.15
    assert "color_cast_blue" in tags
    assert "color_cast_red" not in tags


# ---------------------------------------------------------------------------
# Flat low-contrast gray card -> low_contrast + flat_midtones + low_saturation
# ---------------------------------------------------------------------------


def test_flat_low_contrast_gray(tmp_images):
    rng = np.random.default_rng(0)
    # Narrow range around mid-gray with tiny noise so it isn't literally a
    # single flat color (JPEG would still round-trip fine either way).
    base = 128 + rng.integers(-3, 4, size=(64, 64, 1))
    arr = np.repeat(base, 3, axis=2).astype(np.uint8)
    path = _save(tmp_images, "flat_gray.jpg", arr)

    result = histogram.analyze(path)
    stats = result["stats"]
    tags = result["issue_tags"]

    assert stats["dynamic_range_score"] < histogram.LOW_CONTRAST_RANGE_SCORE
    assert stats["mean_saturation"] < histogram.LOW_SATURATION_THRESHOLD
    assert "low_contrast" in tags
    assert "flat_midtones" in tags
    assert "low_saturation" in tags


# ---------------------------------------------------------------------------
# High ISO + no denoise/sharpen modules enabled -> no_denoise_enabled /
# no_sharpening_enabled, gated on EXIF / enabled_modules
# ---------------------------------------------------------------------------


def test_high_iso_without_denoise_flags_tag(tmp_images):
    rng = np.random.default_rng(1)
    # Mid-gray with heavy per-pixel noise standing in for a noisy high-ISO
    # shadow region.
    noisy = np.clip(60 + rng.normal(0, 25, size=(64, 64, 3)), 0, 255).astype(np.uint8)
    path = _save(tmp_images, "noisy.jpg", noisy)

    result = histogram.analyze(path, exif={"iso": 6400}, enabled_modules=[])
    tags = result["issue_tags"]
    assert "no_denoise_enabled" in tags

    # With denoiseprofile already enabled, the tag should not fire again.
    result_with_denoise = histogram.analyze(
        path, exif={"iso": 6400}, enabled_modules=[{"op": "denoiseprofile"}]
    )
    assert "no_denoise_enabled" not in result_with_denoise["issue_tags"]


def test_long_exposure_and_ultra_wide_tags(tmp_images):
    arr = np.full((32, 32, 3), 128, dtype=np.uint8)
    path = _save(tmp_images, "mid.jpg", arr)

    result = histogram.analyze(path, exif={"exposure": 4.0, "focal_length": 14.0})
    tags = result["issue_tags"]
    assert "long_exposure_hot_pixels_check" in tags
    assert "ultra_wide_lens_correction_check" in tags

    # A lens-correction module already enabled suppresses the ultra-wide tag.
    result2 = histogram.analyze(
        path, exif={"focal_length": 14.0}, enabled_modules=[{"op": "lens"}]
    )
    assert "ultra_wide_lens_correction_check" not in result2["issue_tags"]


# ---------------------------------------------------------------------------
# compute_stats shape sanity
# ---------------------------------------------------------------------------


def test_compute_stats_shape(tmp_images):
    arr = np.full((16, 16, 3), 100, dtype=np.uint8)
    path = _save(tmp_images, "shape.jpg", arr)

    stats = histogram.compute_stats(path)
    assert stats["width"] == 16
    assert stats["height"] == 16
    for channel in ("r", "g", "b"):
        assert len(stats["per_channel"][channel]["histogram"]) == 256
    assert len(stats["luma"]["histogram"]) == 256
    assert set(stats["luma_percentiles"]) == {"p1", "p5", "p50", "p95", "p99"}
