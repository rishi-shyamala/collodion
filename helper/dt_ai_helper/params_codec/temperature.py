"""Codec for the `temperature` (white balance) module
(`dt_iop_temperature_params_t`).

Ground truth: src/iop/temperature.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(3, dt_iop_temperature_params_t)` - only modversion
3 implemented.

Important: the stored params are the raw per-channel *multipliers* (red,
green, blue, second-green for X-Trans/four-colour sensors), not
Kelvin/tint. darktable computes the Kelvin/tint slider display from these
via a lookup against a blackbody locus - reproducing that conversion is out
of scope here; we surface the multipliers directly with unit annotation so
the assistant doesn't misreport them as Kelvin.
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "temperature"

_V3_FIELDS = [
    FieldSpec("red", "f"),  # channel multiplier
    FieldSpec("green", "f"),  # channel multiplier
    FieldSpec("blue", "f"),  # channel multiplier
    FieldSpec("g2", "f"),  # second green channel multiplier ("various" in source)
]

_CODEC = VersionedStructCodec(OP, {3: _V3_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
