"""Codec for the `exposure` module (`dt_iop_exposure_params_t`).

Ground truth: src/iop/exposure.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(6, dt_iop_exposure_params_t)` - only modversion 6
(the current one) is implemented; see `legacy_params()` in the source for
the v2-v5 layouts if older-version support is ever needed. All decode
targets degrade to `None` for unhandled versions (registry contract).
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "exposure"

_MODE = {0: "manual", 1: "deflicker"}

_V6_FIELDS = [
    FieldSpec("mode", "i", enum=_MODE),
    FieldSpec("black", "f"),  # black level correction, EV
    FieldSpec("exposure", "f"),  # exposure_ev, EV
    FieldSpec("deflicker_percentile", "f"),  # percent
    FieldSpec("deflicker_target_level", "f"),  # EV
    FieldSpec("compensate_exposure_bias", "b"),
]

_CODEC = VersionedStructCodec(OP, {6: _V6_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
