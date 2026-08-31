"""`.dtstyle` XML emitter and recommendation->style translator.

Implements plan `darktableaiassistantplan.md` §7.4 / §5.5 / Phase 5:

- `build_style()` takes a list of already-resolved module param dicts and
  emits a `.dtstyle` XML document, using the Tier-1 `params_codec` encoders
  (plan §7.3) for `op_params` and a hand-derived default
  `dt_develop_blend_params_t` blob (see
  `documentation/agent-insights/007-blendop-defaults.md`) for
  `blendop_params`. Every emitted op is round-trip validated (encode then
  decode, compared against the input values) before being included.
- `translate_recommendation()` maps an Optimize-style structured
  recommendation (plan §5.5) onto codec field names/values for Tier-1 ops,
  using a per-op control-name mapping and light unit parsing (`"+0.5 EV"`
  -> `0.5`, `"75%"` -> `75.0`, `"on"`/`"off"` -> bool). Modules with no
  known codec, no known default parameters, or recommendations that don't
  map to any recognized control still surface as `skipped` entries with a
  human-readable reason so the caller can render manual steps.

XML shape (`<darktable_style version="1.0"><info>...</info><style>
<plugin>...</plugin>...</style></darktable_style>`, `<plugin>` children
`num`/`module`/`operation`/`op_params`/`enabled`/`blendop_params`/
`blendop_version`/`multi_priority`/`multi_name`/`multi_name_hand_edited`)
was verified against darktable's own writer, `dt_styles_save_to_file` in
`src/common/styles.c` @ release-4.6.0 - not guessed from the plan prose
alone. Note `module` there is the *modversion* (an int), not the operation
name (matching plan §7.4's "module=modversion" wording); `operation` is
the module's internal string name.
"""

from __future__ import annotations

import math
import re
import struct
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .params_codec import decode_params, encode_params, supported_versions
from .xmp import encode_params_blob

# ---------------------------------------------------------------------------
# blendop_params defaults (agent-insights 007)
# ---------------------------------------------------------------------------

#: `DEVELOP_BLEND_VERSION` in `src/develop/blend.h` @ release-4.6.0.
BLENDOP_VERSION = 13

# `dt_develop_blend_params_t` (src/develop/blend.h) is entirely 4-byte
# scalar fields plus one fixed char buffer, little-endian, no padding (see
# agent-insights 007 for the full field-by-field derivation):
#   uint32 mask_mode, int32 blend_cst, uint32 blend_mode, float
#   blend_parameter, float opacity, uint32 mask_combine, int32 mask_id
#   (dt_mask_id_t), uint32 blendif, float feathering_radius, uint32
#   feathering_guide, float blur_radius, float contrast, float brightness,
#   float details, uint32 feather_version, uint32 reserved[2], float
#   blendif_parameters[64], float blendif_boost_factors[16], char
#   raster_mask_source[20] (dt_dev_operation_t), int32 raster_mask_instance,
#   int32 raster_mask_id (dt_mask_id_t), int32 raster_mask_invert
#   (gboolean).
_BLENDOP_STRUCT = struct.Struct(
    "<" + "IiIffIiIfIffffI" + "II" + "f" * 64 + "f" * 16 + "20s" + "iii"
)


def _default_blendop_params_bytes() -> bytes:
    """Build the default (no-blending) `dt_develop_blend_params_t` blob.

    Byte-for-byte from `_default_blendop_params` in `src/develop/blend.c`
    @ release-4.6.0 - the struct darktable itself copies in whenever a
    module is enabled without the user ever opening its blend-mode tab
    (`mask_mode = DEVELOP_MASK_DISABLED`, i.e. the module's output is used
    unblended, at full opacity). This is the only blend state
    `params_codec` and the plan's Phase 5 scope cover (masks/parametric
    blending are explicitly out of scope - plan §12).
    """
    scalar_fields = [
        0,  # mask_mode = DEVELOP_MASK_DISABLED
        0,  # blend_cst = DEVELOP_BLEND_CS_NONE
        0x18,  # blend_mode = DEVELOP_BLEND_NORMAL2
        0.0,  # blend_parameter
        100.0,  # opacity (%)
        0,  # mask_combine = DEVELOP_COMBINE_NORM_EXCL (NORM|EXCL == 0)
        0,  # mask_id
        0,  # blendif
        0.0,  # feathering_radius
        5,  # feathering_guide = DEVELOP_MASK_GUIDE_IN_AFTER_BLUR
        0.0,  # blur_radius
        0.0,  # contrast
        0.0,  # brightness
        0.0,  # details (detail mask threshold)
        1,  # feather_version
        0,
        0,  # reserved[2]
    ]
    # blendif_parameters[4 * 16]: { 0,0,1,1 } repeated per channel - "fully
    # open" filter range for all 16 blendif channel slots.
    blendif_parameters = [0.0, 0.0, 1.0, 1.0] * 16
    blendif_boost_factors = [0.0] * 16
    raster_mask_source = b""  # dt_dev_operation_t[20], zero-filled (none)
    # raster_mask_instance, raster_mask_id=INVALID_MASKID, raster_mask_invert=FALSE
    tail = [0, -1, 0]

    return _BLENDOP_STRUCT.pack(
        *scalar_fields, *blendif_parameters, *blendif_boost_factors, raster_mask_source, *tail
    )


#: The default blendop params blob for every emitted plugin entry (plan
#: §7.4: "default `blendop_params` to the standard defaults blob per blend
#: version"). Computed once at import time - it's a pure function of
#: constants, not per-op.
DEFAULT_BLENDOP_PARAMS: bytes = _default_blendop_params_bytes()

assert len(DEFAULT_BLENDOP_PARAMS) == 420, "unexpected dt_develop_blend_params_t size"


# ---------------------------------------------------------------------------
# Factory-default op params (needed because /style receives a
# recommendation, not the current edit state - see module docstring and
# agent-insights 007 for why these are needed and where each value comes
# from).
# ---------------------------------------------------------------------------

#: Per-op, per-field factory defaults transcribed from each op's own
#: `$DEFAULT:` introspection annotation in `src/iop/<op>.c` @
#: release-4.6.0 (darktable's own struct-field-comment convention - not
#: guessed). Used as the base a recommendation's `settings` are overlaid
#: onto, so a recommendation only needs to name the sliders it actually
#: wants to change. `denoiseprofile` has **no** entry: its `a`/`b` noise
#: model coefficients are fit per-camera/per-ISO at runtime
#: (`dt_noiseprofile_*`) and have no meaningful static default, so it can
#: only be styled when the caller supplies a base state (not supported by
#: the current `/style` contract - see agent-insights 007).
DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "exposure": {
        "mode": "manual",
        "black": 0.0,
        "exposure": 0.0,
        "deflicker_percentile": 50.0,
        "deflicker_target_level": -4.0,
        "compensate_exposure_bias": False,
    },
    "filmicrgb": {
        "grey_point_source": 18.45,
        "black_point_source": -8.0,
        "white_point_source": 4.0,
        "reconstruct_threshold": 0.0,
        "reconstruct_feather": 3.0,
        "reconstruct_bloom_vs_details": 100.0,
        "reconstruct_grey_vs_color": 100.0,
        "reconstruct_structure_vs_texture": 0.0,
        "security_factor": 0.0,
        "grey_point_target": 18.45,
        "black_point_target": 0.01517634,
        "white_point_target": 100.0,
        "output_power": 4.0,
        "latitude": 0.01,
        "contrast": 1.0,
        "saturation": 0.0,
        "balance": 0.0,
        "noise_level": 0.2,
        "preserve_color": "rgb_power_norm",
        "version": "v5_2021",
        "auto_hardness": True,
        "custom_grey": False,
        "high_quality_reconstruction": 1,
        "noise_distribution": "gaussian",
        "shadows": "poly_4_hard",
        "highlights": "poly_4_hard",
        "compensate_icc_black": False,
        "spline_version": "v3_2021",
        "enable_highlight_reconstruction": False,
    },
    "sigmoid": {
        "middle_grey_contrast": 1.5,
        "contrast_skewness": 0.0,
        "display_white_target": 100.0,
        "display_black_target": 0.0152,
        "color_processing": "per_channel",
        "hue_preservation": 100.0,
        "red_inset": 0.0,
        "red_rotation": 0.0,
        "green_inset": 0.0,
        "green_rotation": 0.0,
        "blue_inset": 0.0,
        "blue_rotation": 0.0,
        "purity": 0.0,
        "base_primaries": "work_profile",
    },
    "colorbalancergb": {
        "shadows_Y": 0.0,
        "shadows_C": 0.0,
        "shadows_H": 0.0,
        "midtones_Y": 0.0,
        "midtones_C": 0.0,
        "midtones_H": 0.0,
        "highlights_Y": 0.0,
        "highlights_C": 0.0,
        "highlights_H": 0.0,
        "global_Y": 0.0,
        "global_C": 0.0,
        "global_H": 0.0,
        "shadows_weight": 1.0,
        "white_fulcrum": 0.0,
        "highlights_weight": 1.0,
        "chroma_shadows": 0.0,
        "chroma_highlights": 0.0,
        "chroma_global": 0.0,
        "chroma_midtones": 0.0,
        "saturation_global": 0.0,
        "saturation_highlights": 0.0,
        "saturation_midtones": 0.0,
        "saturation_shadows": 0.0,
        "hue_angle": 0.0,
        "brilliance_global": 0.0,
        "brilliance_highlights": 0.0,
        "brilliance_midtones": 0.0,
        "brilliance_shadows": 0.0,
        "mask_grey_fulcrum": 0.1845,
        "vibrance": 0.0,
        "grey_fulcrum": 0.1845,
        "contrast": 0.0,
        "saturation_formula": "darktable_ucs_2022",
    },
    "toneequal": {
        "noise": 0.0,
        "ultra_deep_blacks": 0.0,
        "deep_blacks": 0.0,
        "blacks": 0.0,
        "shadows": 0.0,
        "midtones": 0.0,
        "highlights": 0.0,
        "whites": 0.0,
        "speculars": 0.0,
        "blending": 5.0,
        "smoothing": 1.414213562,
        "feathering": 1.0,
        "quantization": 0.0,
        "contrast_boost": 0.0,
        "exposure_boost": 0.0,
        "details": "eigf",
        "method": "rgb_euclidean_norm",
        "iterations": 1,
    },
    "highlights": {
        "mode": "opposed",
        "blendL": 1.0,
        "blendC": 0.0,
        "strength": 0.0,
        "clip": 1.0,
        "noise_level": 0.0,
        "iterations": 30,
        "scales": "128px",
        "candidating": 0.4,
        "combine": 2.0,
        "recovery": "off",
        "solid_color": 0.0,
    },
    "temperature": {
        "red": 1.0,
        "green": 1.0,
        "blue": 1.0,
        "g2": 1.0,
    },
    "sharpen": {
        "radius": 2.0,
        "amount": 0.5,
        "threshold": 0.5,
    },
    "crop": {
        "cx": 0.0,
        "cy": 0.0,
        "cw": 1.0,
        "ch": 1.0,
        "ratio_n": -1,
        "ratio_d": -1,
    },
}


# ---------------------------------------------------------------------------
# recommendation -> codec field translation (plan §5.5)
# ---------------------------------------------------------------------------


def _normalize_label(label: str) -> str:
    return re.sub(r"[\s_-]+", " ", label.strip().lower()).strip()


#: Per-op {normalized human slider label -> codec field name}. Only
#: covers controls an LLM recommendation is realistically going to name
#: (plan §5.5's `settings: [{"control": str, "value": str}]`); anything
#: else is reported as an unrecognized-control skip rather than guessed.
CONTROL_MAP: dict[str, dict[str, str]] = {
    "exposure": {
        "exposure": "exposure",
        "black": "black",
        "black level": "black",
        "black level correction": "black",
    },
    "filmicrgb": {
        "white relative exposure": "white_point_source",
        "white point": "white_point_source",
        "white relative exposure (scene tab)": "white_point_source",
        "black relative exposure": "black_point_source",
        "black point": "black_point_source",
        "contrast": "contrast",
        "latitude": "latitude",
        "saturation": "saturation",
        "shadows highlights balance": "balance",
        "balance": "balance",
        "middle gray luminance": "grey_point_source",
        "hardness": "output_power",
        "highlight reconstruction": "enable_highlight_reconstruction",
    },
    "sigmoid": {
        "contrast": "middle_grey_contrast",
        "skew": "contrast_skewness",
        "contrast skewness": "contrast_skewness",
        "target white": "display_white_target",
        "target black": "display_black_target",
        "preserve hue": "hue_preservation",
    },
    "colorbalancergb": {
        "global vibrance": "vibrance",
        "vibrance": "vibrance",
        "4 ways contrast": "contrast",
        "contrast": "contrast",
        "global chroma": "chroma_global",
        "global saturation": "saturation_global",
        "global luminance": "global_Y",
        "shadows luminance": "shadows_Y",
        "midtones luminance": "midtones_Y",
        "highlights luminance": "highlights_Y",
        "global hue": "global_H",
    },
    "toneequal": {
        "exposure boost": "exposure_boost",
        "highlights": "highlights",
        "shadows": "shadows",
        "whites": "whites",
        "blacks": "blacks",
        "midtones": "midtones",
        "speculars": "speculars",
    },
    "highlights": {
        "strength": "strength",
        "clipping threshold": "clip",
        "clip": "clip",
        "noise level": "noise_level",
    },
    "temperature": {
        "red": "red",
        "green": "green",
        "blue": "blue",
    },
    "sharpen": {
        "radius": "radius",
        "amount": "amount",
        "threshold": "threshold",
    },
    "denoiseprofile": {
        "strength": "strength",
        "preserve shadows": "shadows",
    },
}

#: Fields that should parse as bool (`"on"/"off"`, `"true"/"false"`)
#: rather than a number.
_BOOL_FIELDS = {
    ("filmicrgb", "enable_highlight_reconstruction"),
}

#: Fields that should parse as int rather than float.
_INT_FIELDS = {
    ("filmicrgb", "high_quality_reconstruction"),
    ("toneequal", "iterations"),
    ("highlights", "iterations"),
}

_TRUE_WORDS = {"on", "true", "yes", "enabled", "1"}
_FALSE_WORDS = {"off", "false", "no", "disabled", "0"}


def _parse_numeric(raw_value: str) -> float:
    """Parse a slider value string with the units an LLM recommendation
    plausibly writes: `"+0.5 EV"`, `"-2ev"`, `"75%"`, `"1.8"`."""
    s = raw_value.strip()
    s = re.sub(r"(?i)\bev\b", "", s)
    s = s.replace("%", "")
    s = s.strip()
    if not s:
        raise ValueError(f"empty numeric value {raw_value!r}")
    try:
        return float(s)
    except ValueError as exc:
        raise ValueError(f"could not parse numeric value {raw_value!r}") from exc


def _parse_value(op: str, field: str, raw_value: str) -> Any:
    if (op, field) in _BOOL_FIELDS:
        word = raw_value.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
        raise ValueError(f"could not parse boolean value {raw_value!r}")
    if (op, field) in _INT_FIELDS:
        return int(round(_parse_numeric(raw_value)))
    return _parse_numeric(raw_value)


def translate_recommendation(
    recommendation: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Translate a plan §5.5 structured recommendation into module dicts
    ready for `build_style()`.

    Returns `(modules, skipped)`:
      - `modules`: `[{"op", "modversion", "values", "enabled", "multi_name",
        "multi_priority"}, ...]` for every recommendation whose module has
        a codec, known defaults, and at least resolves (even if some of its
        individual controls didn't map - those are reported separately).
      - `skipped`: `[{"module", "control", "reason"}, ...]` - one entry per
        unusable module (no codec / no defaults) or per unmapped/unparseable
        control within an otherwise-usable module.
    """
    modules: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for rec in recommendation.get("recommendations", []):
        op = rec.get("module", "")
        versions = supported_versions(op)
        if not versions:
            skipped.append(
                {"module": op, "control": None, "reason": f"no params codec for module {op!r}"}
            )
            continue

        base = DEFAULT_PARAMS.get(op)
        if base is None:
            skipped.append(
                {
                    "module": op,
                    "control": None,
                    "reason": (
                        f"no known default parameters for {op!r}; this module can only be "
                        "styled from a known current-edit-state base, which /style does not "
                        "have"
                    ),
                }
            )
            continue

        values = dict(base)
        mapping = CONTROL_MAP.get(op, {})
        for setting in rec.get("settings", []):
            control = setting.get("control", "")
            raw_value = setting.get("value", "")
            field = mapping.get(_normalize_label(control))
            if field is None:
                skipped.append(
                    {"module": op, "control": control, "reason": "unrecognized control name"}
                )
                continue
            try:
                values[field] = _parse_value(op, field, raw_value)
            except ValueError as exc:
                skipped.append({"module": op, "control": control, "reason": str(exc)})
                continue

        modules.append(
            {
                "op": op,
                "modversion": max(versions),
                "values": values,
                "enabled": True,
                "multi_name": "",
                "multi_priority": 0,
            }
        )

    return modules, skipped


# ---------------------------------------------------------------------------
# .dtstyle XML emitter (plan §7.4)
# ---------------------------------------------------------------------------


def _values_equal(actual: Any, expected: Any) -> bool:
    """Recursive comparison for round-trip validation; floats compare with
    a tolerance (struct fields are 32-bit, plan §7.4 requires round-trip
    validation of the encoded bytes, not bit-identical float64 literals -
    see agent-insights 006's testing note)."""
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-5, abs_tol=1e-6)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_values_equal(actual[k], expected[k]) for k in expected)
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_values_equal(a, e) for a, e in zip(actual, expected, strict=True))
        )
    return actual == expected


def _plugin_element(
    *,
    num: int,
    op: str,
    modversion: int,
    op_params_text: str,
    enabled: bool,
    blendop_params_text: str,
    blendop_version: int,
    multi_priority: int,
    multi_name: str,
) -> ET.Element:
    plugin = ET.Element("plugin")
    fields = [
        ("num", str(num)),
        ("module", str(modversion)),
        ("operation", op),
        ("op_params", op_params_text),
        ("enabled", "1" if enabled else "0"),
        ("blendop_params", blendop_params_text),
        ("blendop_version", str(blendop_version)),
        ("multi_priority", str(multi_priority)),
        ("multi_name", multi_name),
        ("multi_name_hand_edited", "0"),
    ]
    for tag, text in fields:
        ET.SubElement(plugin, tag).text = text
    return plugin


def build_style(name: str, modules: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a `.dtstyle` XML document from resolved module param dicts.

    `modules`: `[{"op", "modversion", "values", "enabled"?, "multi_name"?,
    "multi_priority"?}, ...]` - the shape `translate_recommendation()`
    returns.

    Only ops with a working encoder are emitted; every emitted op is
    validated by decoding the just-encoded bytes back and comparing
    against the input `values` (plan §7.4's round-trip requirement) before
    being included. Returns `{"xml": str, "included_ops": [...],
    "skipped_ops": [{"op", "reason"}, ...]}`.
    """
    included_ops: list[str] = []
    skipped_ops: list[dict[str, str]] = []
    iop_order: list[str] = []
    plugin_elements: list[ET.Element] = []

    for i, module in enumerate(modules):
        op = module["op"]
        modversion = module["modversion"]
        values = module["values"]
        try:
            raw = encode_params(op, modversion, values)
        except ValueError as exc:
            skipped_ops.append({"op": op, "reason": str(exc)})
            continue

        decoded_back = decode_params(op, modversion, raw)
        if decoded_back is None or not _values_equal(decoded_back, values):
            skipped_ops.append({"op": op, "reason": "round-trip validation failed"})
            continue

        plugin_elements.append(
            _plugin_element(
                num=i,
                op=op,
                modversion=modversion,
                op_params_text=encode_params_blob(raw),
                enabled=module.get("enabled", True),
                blendop_params_text=encode_params_blob(DEFAULT_BLENDOP_PARAMS),
                blendop_version=BLENDOP_VERSION,
                multi_priority=module.get("multi_priority", 0),
                multi_name=module.get("multi_name", ""),
            )
        )
        included_ops.append(op)
        iop_order.append(op)

    root = ET.Element("darktable_style", version="1.0")
    info = ET.SubElement(root, "info")
    ET.SubElement(info, "name").text = name
    ET.SubElement(info, "description").text = ""
    if iop_order:
        # Matches `dt_ioppr_serialize_text_iop_order_list`'s flat
        # "operation,instance,operation,instance,..." shape (same one
        # `xmp.py` parses out of `darktable:iop_order_list`).
        ET.SubElement(info, "iop_list").text = ",".join(f"{op},0" for op in iop_order)

    style_el = ET.SubElement(root, "style")
    for plugin in plugin_elements:
        style_el.append(plugin)

    xml_text = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    return {"xml": xml_text, "included_ops": included_ops, "skipped_ops": skipped_ops}


# ---------------------------------------------------------------------------
# Writing the .dtstyle file to disk
# ---------------------------------------------------------------------------


def default_style_dir() -> Path:
    """Best-effort per-platform cache directory for generated `.dtstyle`
    files, mirroring `main.default_runtime_dir()` (kept independent to
    avoid an import cycle: `main` imports `api`, which will import this
    module)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    elif sys.platform.startswith("win"):
        import os

        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        import os

        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "dt-ai-helper" / "styles"


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def slugify_style_name(name: str) -> str:
    slug = _SAFE_NAME_RE.sub("_", name.strip()).strip("_")
    return slug or "ai-style"


def write_style_file(xml_text: str, name: str, directory: Path | None = None) -> Path:
    """Write `xml_text` to `<directory>/<slugified name>.dtstyle`, creating
    `directory` if needed. Returns the written path."""
    target_dir = directory if directory is not None else default_style_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{slugify_style_name(name)}.dtstyle"
    path.write_text(xml_text, encoding="utf-8")
    return path
