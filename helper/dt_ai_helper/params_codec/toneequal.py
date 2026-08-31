"""Codec for the `toneequal` (tone equalizer) module
(`dt_iop_toneequalizer_params_t`).

Ground truth: src/iop/toneequal.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(2, dt_iop_toneequalizer_params_t)` - only
modversion 2 implemented.

Note the `method` field is typed `dt_iop_luminance_mask_method_t`, an enum
shared across several modules, defined in `src/common/luminance_mask.h`
(fetched and transcribed directly - not guessed).
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "toneequal"

_DETAILS_FILTER = {
    0: "none",
    1: "averaged_guided",
    2: "guided",
    3: "averaged_eigf",
    4: "eigf",
}
_LUMINANCE_METHOD = {
    0: "rgb_average",
    1: "hsl_lightness",
    2: "hsv_value",
    3: "rgb_sum",
    4: "rgb_euclidean_norm",
    5: "rgb_power_norm",
    6: "rgb_geometric_mean",
}

_V2_FIELDS = [
    FieldSpec("noise", "f"),  # EV, "blacks"
    FieldSpec("ultra_deep_blacks", "f"),  # EV
    FieldSpec("deep_blacks", "f"),  # EV
    FieldSpec("blacks", "f"),  # EV, "light shadows"
    FieldSpec("shadows", "f"),  # EV, "mid-tones"
    FieldSpec("midtones", "f"),  # EV, "dark highlights"
    FieldSpec("highlights", "f"),  # EV
    FieldSpec("whites", "f"),  # EV
    FieldSpec("speculars", "f"),  # EV
    FieldSpec("blending", "f"),  # smoothing diameter, %
    FieldSpec("smoothing", "f"),
    FieldSpec("feathering", "f"),
    FieldSpec("quantization", "f"),  # EV
    FieldSpec("contrast_boost", "f"),  # EV
    FieldSpec("exposure_boost", "f"),  # EV
    FieldSpec("details", "i", enum=_DETAILS_FILTER),
    FieldSpec("method", "i", enum=_LUMINANCE_METHOD),
    FieldSpec("iterations", "i"),
]

_CODEC = VersionedStructCodec(OP, {2: _V2_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
