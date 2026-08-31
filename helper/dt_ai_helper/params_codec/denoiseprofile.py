"""Codec for the `denoiseprofile` (denoise (profiled)) module
(`dt_iop_denoiseprofile_params_t`).

Ground truth: src/iop/denoiseprofile.c @ darktable release-4.6.0.
`DT_MODULE_INTROSPECTION(11, dt_iop_denoiseprofile_params_t)` - only
modversion 11 implemented; this module has an unusually long legacy chain
(v1-v10) that is not transcribed here (out of scope for Tier 1 - decodes
to `None` for those versions).

Layout notes:
- `a[3]`, `b[3]`: per-RGB-channel Poissonian-Gaussian noise model fit
  coefficients.
- `x[6][7]`, `y[6][7]`: wavelet-band correction curve control points, one
  curve per channel (`DT_DENOISE_PROFILE_NONE` == 6 channels: all, R, G, B,
  Y0, U0V0) with `DT_IOP_DENOISE_PROFILE_BANDS` == 7 points per curve.
  Decoded as nested lists `x[channel][band]`.
"""

from __future__ import annotations

from ._struct_codec import FieldSpec, VersionedStructCodec

OP = "denoiseprofile"

_MODE = {
    0: "nlmeans",
    3: "nlmeans_auto",
    1: "wavelets",
    4: "wavelets_auto",
    2: "compute_variance",
}
_WAVELET_COLOR_MODE = {0: "rgb", 1: "y0u0v0"}

_NUM_CHANNELS = 6  # DT_DENOISE_PROFILE_NONE
_NUM_BANDS = 7  # DT_IOP_DENOISE_PROFILE_BANDS

_V11_FIELDS = [
    FieldSpec("radius", "f"),  # patch size
    FieldSpec("nbhood", "f"),  # search radius
    FieldSpec("strength", "f"),
    FieldSpec("shadows", "f"),  # preserve shadows
    FieldSpec("bias", "f"),  # bias correction
    FieldSpec("scattering", "f"),
    FieldSpec("central_pixel_weight", "f"),
    FieldSpec("overshooting", "f"),
    FieldSpec("a", "f", shape=(3,)),  # noise model fit, per R/G/B
    FieldSpec("b", "f", shape=(3,)),  # noise model fit, per R/G/B
    FieldSpec("mode", "i", enum=_MODE),
    FieldSpec("x", "f", shape=(_NUM_CHANNELS, _NUM_BANDS)),
    FieldSpec("y", "f", shape=(_NUM_CHANNELS, _NUM_BANDS)),
    FieldSpec("wb_adaptive_anscombe", "b"),
    FieldSpec("fix_anscombe_and_nlmeans_norm", "b"),
    FieldSpec("use_new_vst", "b"),
    FieldSpec("wavelet_color_mode", "i", enum=_WAVELET_COLOR_MODE),
]

_CODEC = VersionedStructCodec(OP, {11: _V11_FIELDS})

SUPPORTED_VERSIONS = _CODEC.supported_versions()


def decode(modversion: int, raw: bytes) -> dict | None:
    return _CODEC.decode(modversion, raw)


def encode(modversion: int, values: dict) -> bytes:
    return _CODEC.encode(modversion, values)
