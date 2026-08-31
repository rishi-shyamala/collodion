"""Codec for the `highlights` (highlight reconstruction) module
(`dt_iop_highlights_params_t`).

Ground truth: src/iop/highlights.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(4, dt_iop_highlights_params_t)` - only modversion 4
implemented.
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "highlights"

_MODE = {
    5: "opposed",
    1: "reconstruct_lch",
    0: "clip",
    4: "segmentation_based",
    3: "guided_laplacians",
    2: "reconstruct_color",
}
_SCALES = {
    0: "2px",
    1: "4px",
    2: "8px",
    3: "16px",
    4: "32px",
    5: "64px",
    6: "128px",
    7: "256px",
    8: "512px",
    9: "1024px",
    10: "2048px",
    11: "4096px",
}
_RECOVERY = {
    0: "off",
    5: "generic",
    6: "flat_generic",
    1: "small_segments",
    2: "large_segments",
    3: "flat_small_segments",
    4: "flat_large_segments",
}

_V4_FIELDS = [
    FieldSpec("mode", "i", enum=_MODE),
    FieldSpec("blendL", "f"),  # unused
    FieldSpec("blendC", "f"),  # unused
    FieldSpec("strength", "f"),
    FieldSpec("clip", "f"),  # clipping threshold
    FieldSpec("noise_level", "f"),
    FieldSpec("iterations", "i"),
    FieldSpec("scales", "i", enum=_SCALES),  # reconstruction diameter
    FieldSpec("candidating", "f"),
    FieldSpec("combine", "f"),
    FieldSpec("recovery", "i", enum=_RECOVERY),
    FieldSpec("solid_color", "f"),
]

_CODEC = VersionedStructCodec(OP, {4: _V4_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
