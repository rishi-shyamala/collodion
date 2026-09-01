#!/usr/bin/env python3
"""Generate the `generated_tier1.xmp` / `generated_tier1.yaml` fixture pair.

There is no darktable install available in this environment, so real
darktable-produced sidecars can't be captured here. Instead, this script
builds a *plausible* XMP sidecar by running known parameter dicts for every
Tier-1 module through our own `params_codec` encoders (the same encoders
`styles.py` will use), following the exact `darktable:history` shape and
`gz`/plain-hex `darktable:params` encoding documented in
`documentation/agent-insights/005-xmp-params-encoding.md`.

This validates internal consistency (xmp.py's parsing + each codec's
decode() agree with what encode() + the gz/hex writer produced) but is
**not** a substitute for real fixtures. Capturing actual XMPs from
darktable 4.6/5.x with known slider values, saved next to a YAML of the
values set in the GUI, remains an outstanding manual task - see the
insights doc.

Usage: `python tests/fixtures/make_fixtures.py` (run from anywhere; regenerates
generated_tier1.xmp and generated_tier1.yaml in this directory).
"""

from __future__ import annotations

import base64
import sys
import zlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

import yaml

_HELPER_SRC = Path(__file__).resolve().parents[2] / "helper"
if str(_HELPER_SRC) not in sys.path:
    sys.path.insert(0, str(_HELPER_SRC))

from dt_ai_helper.params_codec import encode_params  # noqa: E402 -- needs the sys.path fix-up above

# Matches src/common/exif.cc COMPRESS_THRESHOLD + the "only large entries"
# compress_xmp_tags preference, which is darktable's default.
COMPRESS_THRESHOLD = 100

FIXTURE_DIR = Path(__file__).resolve().parent

# (op, modversion, values) in the order they'll appear in the history stack
# and in darktable:iop_order_list. Values are chosen to be human-plausible
# edits, not defaults, so a decode bug that silently returns defaults would
# be caught.
FIXTURE_MODULES: list[tuple[str, int, dict]] = [
    (
        "temperature",
        3,
        {"red": 2.398, "green": 1.0, "blue": 1.522, "g2": 1.0},
    ),
    (
        "highlights",
        4,
        {
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
    ),
    (
        "denoiseprofile",
        11,
        {
            "radius": 1.0,
            "nbhood": 7.0,
            "strength": 1.0,
            "shadows": 1.0,
            "bias": 0.0,
            "scattering": 0.0,
            "central_pixel_weight": 0.1,
            "overshooting": 1.0,
            "a": [0.01, 0.011, 0.012],
            "b": [0.0005, 0.00055, 0.0006],
            "mode": "wavelets",
            "x": [[0.0, 0.1667, 0.3333, 0.5, 0.6667, 0.8333, 1.0] for _ in range(6)],
            "y": [[0.5] * 7 for _ in range(6)],
            "wb_adaptive_anscombe": True,
            "fix_anscombe_and_nlmeans_norm": True,
            "use_new_vst": True,
            "wavelet_color_mode": "y0u0v0",
        },
    ),
    (
        "exposure",
        6,
        {
            "mode": "manual",
            "black": -0.02,
            "exposure": 0.65,
            "deflicker_percentile": 50.0,
            "deflicker_target_level": -4.0,
            "compensate_exposure_bias": False,
        },
    ),
    (
        "filmicrgb",
        6,
        {
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
            "black_point_target": 0.0152,
            "white_point_target": 100.0,
            "output_power": 4.0,
            "latitude": 0.01,
            "contrast": 1.2,
            "saturation": 0.0,
            "balance": 0.0,
            "noise_level": 0.2,
            "preserve_color": "rgb_power_norm",
            "version": "v7_2023",
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
    ),
    (
        "sigmoid",
        3,
        {
            "middle_grey_contrast": 1.7,
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
    ),
    (
        "colorbalancergb",
        5,
        {
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
            "vibrance": 0.05,
            "grey_fulcrum": 0.1845,
            "contrast": 0.1,
            "saturation_formula": "darktable_ucs_2022",
        },
    ),
    (
        "toneequal",
        2,
        {
            "noise": 0.0,
            "ultra_deep_blacks": 0.0,
            "deep_blacks": 0.0,
            "blacks": 0.3,
            "shadows": 0.2,
            "midtones": 0.0,
            "highlights": -0.2,
            "whites": -0.3,
            "speculars": 0.0,
            "blending": 5.0,
            "smoothing": 1.4142,
            "feathering": 1.0,
            "quantization": 0.0,
            "contrast_boost": 0.0,
            "exposure_boost": 0.0,
            "details": "eigf",
            "method": "rgb_euclidean_norm",
            "iterations": 1,
        },
    ),
    (
        "sharpen",
        1,
        {"radius": 2.0, "amount": 0.5, "threshold": 0.5},
    ),
    (
        "crop",
        1,
        {"cx": 0.02, "cy": 0.02, "cw": 0.98, "ch": 0.98, "ratio_n": -1, "ratio_d": -1},
    ),
]


def encode_field(op: str, modversion: int, values: dict) -> str:
    """Encode `values` the way darktable would write `darktable:params`:
    gz-compressed+base64 above COMPRESS_THRESHOLD raw bytes, plain hex
    otherwise (see src/common/exif.cc dt_exif_xmp_encode)."""
    raw = encode_params(op, modversion, values)
    if len(raw) > COMPRESS_THRESHOLD:
        compressed = zlib.compress(raw)
        factor = min(len(raw) // max(len(compressed), 1) + 1, 99)
        return f"gz{factor:02d}" + base64.b64encode(compressed).decode("ascii")
    return raw.hex()


def build_xmp() -> str:
    iop_order_list = ",".join(f"{op},0" for op, _v, _values in FIXTURE_MODULES)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="dt-ai-helper make_fixtures.py">',
        ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '  <rdf:Description rdf:about=""',
        '    xmlns:darktable="http://darktable.sf.net/"',
        '    darktable:xmp_version="4"',
        '    darktable:raw_params="0"',
        f'    darktable:history_end="{len(FIXTURE_MODULES)}"',
        '    darktable:iop_order_version="1"',
        f"    darktable:iop_order_list={quoteattr(iop_order_list)}>",
        "   <darktable:history>",
        "    <rdf:Seq>",
    ]
    for num, (op, modversion, values) in enumerate(FIXTURE_MODULES):
        params_hex_or_gz = encode_field(op, modversion, values)
        lines.append(
            "     <rdf:li\n"
            f'      darktable:num="{num}"\n'
            f'      darktable:operation="{op}"\n'
            '      darktable:enabled="1"\n'
            f'      darktable:modversion="{modversion}"\n'
            f"      darktable:params={quoteattr(params_hex_or_gz)}\n"
            '      darktable:multi_name=""\n'
            '      darktable:multi_name_hand_edited="0"\n'
            '      darktable:multi_priority="0"\n'
            '      darktable:blendop_version="7"/>'
        )
    lines += [
        "    </rdf:Seq>",
        "   </darktable:history>",
        "  </rdf:Description>",
        " </rdf:RDF>",
        "</x:xmpmeta>",
        "",
    ]
    return "\n".join(lines)


def build_expected() -> dict:
    return {
        "history_source": "xmp",
        "iop_order": [op for op, _v, _values in FIXTURE_MODULES],
        "enabled_modules": [
            {
                "op": op,
                "label": op,
                "enabled": True,
                "multi_name": "",
                "multi_priority": 0,
                "modversion": modversion,
                "params_decoded": values,
            }
            for op, modversion, values in FIXTURE_MODULES
        ],
    }


def main() -> None:
    xmp_path = FIXTURE_DIR / "generated_tier1.xmp"
    yaml_path = FIXTURE_DIR / "generated_tier1.yaml"
    xmp_path.write_text(build_xmp(), encoding="utf-8")
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(build_expected(), f, sort_keys=False)
    print(f"wrote {xmp_path}")
    print(f"wrote {yaml_path}")


if __name__ == "__main__":
    main()
