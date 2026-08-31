"""Codec for the `crop` module (`dt_iop_crop_params_t`).

Ground truth: src/iop/crop.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(1, dt_iop_crop_params_t)` - the struct has never
been versioned past 1. This is the current crop module (the old
`clip_rotate`/legacy "clipping" op was renamed/replaced; there is no
separate "clip" op in modern darktable to also codec for).

cx/cy/cw/ch are normalized [0,1] fractional boundaries of the crop
rectangle relative to the full input image (left, top, right, bottom),
*not* width/height - `cw`/`ch` are the right/bottom edge positions, so the
crop width in fraction-of-image terms is `cw - cx` (similarly for height).
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "crop"

_V1_FIELDS = [
    FieldSpec("cx", "f"),  # left edge, fraction of image width
    FieldSpec("cy", "f"),  # top edge, fraction of image height
    FieldSpec("cw", "f"),  # right edge, fraction of image width
    FieldSpec("ch", "f"),  # bottom edge, fraction of image height
    FieldSpec("ratio_n", "i"),  # aspect ratio numerator, -1 = free/off
    FieldSpec("ratio_d", "i"),  # aspect ratio denominator, -1 = free/off
]

_CODEC = VersionedStructCodec(OP, {1: _V1_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
