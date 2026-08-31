"""Codec for the `filmicrgb` module (`dt_iop_filmicrgb_params_t`).

Ground truth: src/iop/filmicrgb.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(6, dt_iop_filmicrgb_params_t)` - only modversion 6
implemented.
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "filmicrgb"

_PRESERVE_COLOR = {
    0: "none",
    1: "max_rgb",
    2: "luminance_y",
    3: "rgb_power_norm",
    4: "rgb_euclidean_norm_v1",
    5: "rgb_euclidean_norm_v2",
}
_COLORSCIENCE = {0: "v3_2019", 1: "v4_2020", 2: "v5_2021", 3: "v6_2022", 4: "v7_2023"}
_CURVE_TYPE = {0: "poly_4_hard", 1: "poly_3_soft", 2: "rational_safe"}
_NOISE_DIST = {0: "uniform", 1: "gaussian", 2: "poissonian"}
_SPLINE_VERSION = {0: "v1_2019", 1: "v2_2020", 2: "v3_2021"}

_V6_FIELDS = [
    FieldSpec("grey_point_source", "f"),  # %
    FieldSpec("black_point_source", "f"),  # EV
    FieldSpec("white_point_source", "f"),  # EV
    FieldSpec("reconstruct_threshold", "f"),  # EV
    FieldSpec("reconstruct_feather", "f"),  # EV
    FieldSpec("reconstruct_bloom_vs_details", "f"),  # %
    FieldSpec("reconstruct_grey_vs_color", "f"),  # %
    FieldSpec("reconstruct_structure_vs_texture", "f"),  # %
    FieldSpec("security_factor", "f"),  # %
    FieldSpec("grey_point_target", "f"),  # %
    FieldSpec("black_point_target", "f"),  # %
    FieldSpec("white_point_target", "f"),  # %
    FieldSpec("output_power", "f"),
    FieldSpec("latitude", "f"),  # %
    FieldSpec("contrast", "f"),
    FieldSpec("saturation", "f"),  # %
    FieldSpec("balance", "f"),  # %
    FieldSpec("noise_level", "f"),
    FieldSpec("preserve_color", "i", enum=_PRESERVE_COLOR),
    FieldSpec("version", "i", enum=_COLORSCIENCE),
    FieldSpec("auto_hardness", "b"),
    FieldSpec("custom_grey", "b"),
    FieldSpec("high_quality_reconstruction", "i"),  # iterations
    FieldSpec("noise_distribution", "i", enum=_NOISE_DIST),
    FieldSpec("shadows", "i", enum=_CURVE_TYPE),
    FieldSpec("highlights", "i", enum=_CURVE_TYPE),
    FieldSpec("compensate_icc_black", "b"),
    FieldSpec("spline_version", "i", enum=_SPLINE_VERSION),
    FieldSpec("enable_highlight_reconstruction", "b"),
]

_CODEC = VersionedStructCodec(OP, {6: _V6_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
