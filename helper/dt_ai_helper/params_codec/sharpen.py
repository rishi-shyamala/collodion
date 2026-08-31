"""Codec for the legacy `sharpen` module (`dt_iop_sharpen_params_t`).

Ground truth: src/iop/sharpen.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(1, dt_iop_sharpen_params_t)` - the struct has never
been versioned past 1.

Note: darktable 4.6+'s default sharpening tool for new edits is actually
`diffuse` (contrast equalizer / diffuse-or-sharpen), a much larger and more
complex module; `sharpen` is the older, still-supported "usm"-style
module explicitly named in plan Tier 1. `diffuse` is not covered by this
codec and decodes to `None` (unknown module) until a follow-up adds it.
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "sharpen"

_V1_FIELDS = [
    FieldSpec("radius", "f"),  # px
    FieldSpec("amount", "f"),
    FieldSpec("threshold", "f"),
]

_CODEC = VersionedStructCodec(OP, {1: _V1_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
