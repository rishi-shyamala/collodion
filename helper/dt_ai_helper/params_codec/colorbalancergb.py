"""Codec for the `colorbalancergb` module (`dt_iop_colorbalancergb_params_t`).

Ground truth: src/iop/colorbalancergb.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(5, dt_iop_colorbalancergb_params_t)` - only
modversion 5 implemented. The struct is explicitly append-only (comment in
source: "add future params after this so the legacy params import can use
a blind memcpy"), so v1-v4 payloads are simply this struct's byte layout
truncated - not implemented here since darktable itself upgrades old
history via `legacy_params` well before params reach an XMP at
modversion 5, but flagged in insights doc as a possible cheap follow-up
(prefix-decode with defaults for the tail).
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "colorbalancergb"

_SATURATION_FORMULA = {0: "jzazbz_2021", 1: "darktable_ucs_2022"}

_V5_FIELDS = [
    # v1
    FieldSpec("shadows_Y", "f"),
    FieldSpec("shadows_C", "f"),
    FieldSpec("shadows_H", "f"),  # degrees
    FieldSpec("midtones_Y", "f"),
    FieldSpec("midtones_C", "f"),
    FieldSpec("midtones_H", "f"),  # degrees
    FieldSpec("highlights_Y", "f"),
    FieldSpec("highlights_C", "f"),
    FieldSpec("highlights_H", "f"),  # degrees
    FieldSpec("global_Y", "f"),
    FieldSpec("global_C", "f"),
    FieldSpec("global_H", "f"),  # degrees
    FieldSpec("shadows_weight", "f"),
    FieldSpec("white_fulcrum", "f"),  # EV
    FieldSpec("highlights_weight", "f"),
    FieldSpec("chroma_shadows", "f"),
    FieldSpec("chroma_highlights", "f"),
    FieldSpec("chroma_global", "f"),
    FieldSpec("chroma_midtones", "f"),
    FieldSpec("saturation_global", "f"),
    FieldSpec("saturation_highlights", "f"),
    FieldSpec("saturation_midtones", "f"),
    FieldSpec("saturation_shadows", "f"),
    FieldSpec("hue_angle", "f"),  # degrees
    # v2
    FieldSpec("brilliance_global", "f"),
    FieldSpec("brilliance_highlights", "f"),
    FieldSpec("brilliance_midtones", "f"),
    FieldSpec("brilliance_shadows", "f"),
    # v3
    FieldSpec("mask_grey_fulcrum", "f"),
    # v4
    FieldSpec("vibrance", "f"),
    FieldSpec("grey_fulcrum", "f"),
    FieldSpec("contrast", "f"),
    # v5
    FieldSpec("saturation_formula", "i", enum=_SATURATION_FORMULA),
]

_CODEC = VersionedStructCodec(OP, {5: _V5_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
