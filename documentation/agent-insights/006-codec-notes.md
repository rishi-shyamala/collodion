# 006 — Params codec notes (Tier 1)

Worker: W4 (`feat/xmp-codecs`). Ground truth for every struct layout below
was fetched directly from `src/iop/<op>.c` (and, for one shared enum,
`src/common/luminance_mask.h`) at darktable tag `release-4.6.0` via
`raw.githubusercontent.com` and transcribed field-by-field — none of this
was guessed from memory or documentation prose. GitHub's code-search API
(`gh api search/code -f q='SYMBOL repo:darktable-org/darktable'`) was
useful for chasing enum/type definitions that live outside the op's own
`.c` file.

## Shared implementation note (applies to every module below)

All Tier-1 structs are packing-friendly: every field is exactly 4 bytes
(`float`, `int`, C `enum` — darktable's introspection enums are `int`-sized
— or `gboolean`, which is glib's `int` typedef). None of the covered
structs mixes in an 8-byte type ahead of a scalar tail, so there is **no
compiler padding** to account for anywhere in this list; the in-memory
layout is exactly the field declaration order. See
`helper/dt_ai_helper/params_codec/_struct_codec.py` for the shared
`FieldSpec`/`VersionedStructCodec` machinery this relies on. All packing
uses little-endian (`<`) — every platform darktable ships on is
little-endian, and the params blob is a verbatim memory dump written and
read back on that architecture.

**Only the current (highest) modversion is implemented for every op.**
Plan §7.3 says unknown-modversion degrades to `decoded: null`, so an older
XMP (written by a pre-4.6 darktable that never got its history upgraded)
will show the module as enabled but undecoded rather than crash or
misdecode — this is by design, not an oversight, except where noted
below as a possible cheap follow-up.

## Per-module notes

### exposure (`dt_iop_exposure_params_t`, modversion 6)
6 fields, 24 bytes: `mode`(enum: manual/deflicker), `black`, `exposure`,
`deflicker_percentile`, `deflicker_target_level`,
`compensate_exposure_bias`(bool). Straightforward; legacy v2–v5 layouts
are documented in the module's own `legacy_params()` if ever needed.

### filmicrgb (`dt_iop_filmicrgb_params_t`, modversion 6)
29 fields, 116 bytes. Five enums (`preserve_color`, `version`
[colorscience], `noise_distribution`, `shadows`/`highlights`
[curve type], `spline_version`) — all transcribed from the `$DESCRIPTION`
introspection comments in the source, which double as the exact
human-facing labels darktable's own UI uses. `version` here means "color
science version" (v3_2019 .. v7_2023), not the modversion — don't confuse
the two when reading decoded output.

### sigmoid (`dt_iop_sigmoid_params_t`, modversion 3)
14 fields, 56 bytes. Recently-introduced module (shipped alongside
filmicrgb as the newer scene-referred tone mapper); only one modversion
has ever existed, so there's no legacy chain to worry about.

### colorbalancergb (`dt_iop_colorbalancergb_params_t`, modversion 5)
33 fields, 132 bytes. The struct's own comments mark which fields belong
to which historical version (v1 through v5) and explicitly say new fields
must be *appended*, "so the legacy params import can use a blind memcpy" —
i.e. darktable itself treats v1–v4 payloads as byte-prefixes of the v5
struct. **Possible cheap follow-up**: a v1–v4 decoder could be built as
"unpack the first N fields, default the rest" rather than a full separate
`FieldSpec` list, since it's a true prefix relationship here (verify this
against `legacy_params()` before relying on it, in case any transform
beyond padding happens on upgrade).

### toneequal (`dt_iop_toneequalizer_params_t`, modversion 2)
18 fields, 72 bytes. The `method` field's type,
`dt_iop_luminance_mask_method_t`, is *not* defined in `toneequal.c` — it
lives in `src/common/luminance_mask.h` and is shared with other modules.
Fetched separately; enum values are `DT_TONEEQ_MEAN=0`,
`_LIGHTNESS=1`, `_VALUE=2`, `_NORM_1=3`, `_NORM_2=4`, `_NORM_POWER=5`,
`_GEOMEAN=6`. (The `details` field's type, `dt_iop_toneequalizer_filter_t`,
*is* local to `toneequal.c` and named `DT_TONEEQ_*` too — same prefix,
different enum; don't conflate the two `DT_TONEEQ_*` families when cross
-referencing source.)

### highlights (`dt_iop_highlights_params_t`, modversion 4)
12 fields, 48 bytes. Note the `mode` enum's integer values are **not** in
declaration order (`OPPOSED=5, LCH=1, CLIP=0, SEGMENTS=4, LAPLACIAN=3,
INPAINT=2`) — copy the explicit `= N` values, don't assume positional
enum numbering here. `blendL`/`blendC` are marked "unused" in the source
comment but are still real struct fields occupying real bytes — they must
still be encoded/decoded to keep the struct size and byte layout correct,
even though they carry no meaningful signal.

### temperature (`dt_iop_temperature_params_t`, modversion 3)
4 fields, 16 bytes: `red`, `green`, `blue`, and a 4th field the source
names `various` (renamed `g2` in our codec for clarity — it's the second
green channel multiplier used by 4-channel/X-Trans sensors). **Important
for consumers of decoded output**: these are raw per-channel
*multipliers*, not Kelvin/tint. darktable's UI derives the
Kelvin/tint sliders from these via a blackbody-locus lookup that is not
reproduced here — don't have the assistant claim a decoded Kelvin value
from this codec's output.

### sharpen (`dt_iop_sharpen_params_t`, modversion 1)
3 fields, 12 bytes: `radius`, `amount`, `threshold`. This is darktable's
older "usm"-style module, still shipped and still what the plan names
under Tier 1 as `sharpen`/`diffuse`. **Not covered**: `diffuse` (the
newer, much larger diffuse-or-sharpen/contrast-equalizer module that is
the default new-edit sharpening tool in 4.6+) is a materially different,
much bigger struct and is out of scope for this pass — it decodes to
`None` (unknown op) until a follow-up adds a dedicated codec.

### denoiseprofile (`dt_iop_denoiseprofile_params_t`, modversion 11)
17 fields (some are fixed-size C arrays), 412 bytes — the largest Tier-1
struct by far. Two 3-element arrays (`a`, `b`: per-RGB-channel
Poissonian-Gaussian noise-model fit coefficients) and two `[6][7]`
2D arrays (`x`, `y`: wavelet-band correction curve control points, 6
channels × 7 band points each, where 6 = `DT_DENOISE_PROFILE_NONE` and 7 =
`DT_IOP_DENOISE_PROFILE_BANDS`). This is the reason
`_struct_codec.FieldSpec` supports a `shape` tuple and nested-list
decode/encode (`_reshape`/`_flatten`) rather than only scalars — every
other Tier-1 module only needed scalars. **Not covered**: this module has
an unusually long legacy chain (v1 through v10) that is not transcribed —
older-version XMPs degrade to `None` per the standard contract.

### crop (`dt_iop_crop_params_t`, modversion 1)
6 fields, 24 bytes: `cx`, `cy`, `cw`, `ch` (fractional **edge positions**,
not width/height — e.g. crop width as a fraction of the image is `cw -
cx`, not `cw` itself), plus `ratio_n`/`ratio_d` (aspect ratio numerator/
denominator, `-1` meaning "free"/off). This is darktable's *current* crop
module — there is no separate modern "clip" op to also cover; the plan's
"crop/clip" naming refers to this one module under its old alias.

## Testing note

Because every field is a 32-bit float or int, decode(encode(x)) is only
guaranteed **value-close**, not bit-identical to an arbitrary Python
float literal (e.g. `18.45` round-trips through `float32` as
`18.450000762939453`). Tests compare with `pytest.approx` for this
reason; byte-exactness is instead verified directly by checking
`encode(decode(raw)) == raw` (round-tripping the *bytes*, not a literal),
which is the property that actually matters for `styles.py`'s use of these
encoders.
