"""Codec for the `sigmoid` module (`dt_iop_sigmoid_params_t`).

Ground truth: src/iop/sigmoid.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(3, dt_iop_sigmoid_params_t)` - only modversion 3
implemented (the module was introduced shortly before 4.6; no older
layout is in wide use).
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "sigmoid"

_METHOD = {0: "per_channel", 1: "rgb_ratio"}
_BASE_PRIMARIES = {
    0: "work_profile",
    1: "rec2020",
    2: "display_p3",
    3: "adobe_rgb",
    4: "srgb",
}

_V3_FIELDS = [
    FieldSpec("middle_grey_contrast", "f"),
    FieldSpec("contrast_skewness", "f"),
    FieldSpec("display_white_target", "f"),  # cd/m2-ish target white
    FieldSpec("display_black_target", "f"),  # target black
    FieldSpec("color_processing", "i", enum=_METHOD),
    FieldSpec("hue_preservation", "f"),  # %
    FieldSpec("red_inset", "f"),
    FieldSpec("red_rotation", "f"),
    FieldSpec("green_inset", "f"),
    FieldSpec("green_rotation", "f"),
    FieldSpec("blue_inset", "f"),
    FieldSpec("blue_rotation", "f"),
    FieldSpec("purity", "f"),
    FieldSpec("base_primaries", "i", enum=_BASE_PRIMARIES),
]

_CODEC = VersionedStructCodec(OP, {3: _V3_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
