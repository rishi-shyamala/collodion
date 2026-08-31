# 007 — `.dtstyle` emitter: blendop defaults, op defaults, `/style` contract

Worker: W7 (`feat/styles`), plan Phase 5 ("apply via styles"). Ground
truth fetched directly from `src/develop/blend.h`, `src/develop/blend.c`,
and each op's own `src/iop/<op>.c` at darktable tag `release-4.6.0` via
`raw.githubusercontent.com` — none of this was guessed. Implementation:
`helper/dt_ai_helper/styles.py`.

## 1. `.dtstyle` XML shape (verified against darktable's own writer)

The plan (§7.4) describes `<plugin>` entries as carrying fields but doesn't
pin down whether they're XML attributes or child elements. Checked
`dt_styles_save_to_file` in `src/common/styles.c` @ release-4.6.0 directly:
they're **child elements**, not attributes, and the full field list/order
darktable itself writes is:

```xml
<darktable_style version="1.0">
  <info>
    <name>...</name>
    <description>...</description>
    <iop_list>op,instance,op,instance,...</iop_list>  <!-- omitted if empty -->
  </info>
  <style>
    <plugin>
      <num>0</num>
      <module>6</module>              <!-- modversion, NOT the op name -->
      <operation>exposure</operation>  <!-- the op name -->
      <op_params>...</op_params>
      <enabled>1</enabled>
      <blendop_params>...</blendop_params>
      <blendop_version>13</blendop_version>
      <multi_priority>0</multi_priority>
      <multi_name></multi_name>
      <multi_name_hand_edited>0</multi_name_hand_edited>
    </plugin>
    ...
  </style>
</darktable_style>
```

Confirms the plan's "module=modversion" wording literally — the `<module>`
element is the int `modversion`, and `<operation>` is the string op name.
Our emitter (`styles.build_style`) reproduces this exactly, including
`blendop_version` and `multi_name_hand_edited` (not explicitly named in
the plan's field list but present in every real style file and cheap to
emit correctly).

**`op_params`/`blendop_params` encoding**: `src/common/styles.c::dt_style_encode`
calls `dt_exif_xmp_encode` — the *same* gz/plain-hex routine XMP sidecars
use (agent-insights 005). So `xmp.py`'s `decode_params_blob` already
decodes style files' `op_params`/`blendop_params` with no changes needed;
this worker added `xmp.encode_params_blob()` as its encode twin (mirrors
`tests/fixtures/make_fixtures.py::encode_field`, which now could be
refactored to call it — not done here to avoid touching another worker's
test fixture script without cause).

## 2. Default `blendop_params` blob

`dt_develop_blend_params_t` (`src/develop/blend.h`, `DEVELOP_BLEND_VERSION
= 13` at this tag) is, like every Tier-1 op struct, built entirely from
4-byte scalars plus one fixed char buffer — no padding — but resolving the
buffer's type required chasing two typedefs across headers not included
directly by `blend.h`:

- `dt_mask_id_t` → `int32_t` (`src/common/darktable.h:167`).
- `dt_dev_operation_t` (the type of `raster_mask_source`) → `typedef char
  dt_dev_operation_t[20]` (`src/control/settings.h:40` — *not* in
  `develop/imageop.h`, `develop/pixelpipe.h`, or `common/opencl.h`, all of
  which reference the type but don't define it; found by grepping every
  header `blend.h`/`imageop.h` transitively include).

Full field list, in declaration order, 420 bytes total:

| field | C type | bytes |
|---|---|---|
| mask_mode | uint32 | 4 |
| blend_cst | int32 | 4 |
| blend_mode | uint32 | 4 |
| blend_parameter | float | 4 |
| opacity | float | 4 |
| mask_combine | uint32 | 4 |
| mask_id | dt_mask_id_t (int32) | 4 |
| blendif | uint32 | 4 |
| feathering_radius | float | 4 |
| feathering_guide | uint32 | 4 |
| blur_radius | float | 4 |
| contrast | float | 4 |
| brightness | float | 4 |
| details | float | 4 |
| feather_version | uint32 | 4 |
| reserved[2] | uint32[2] | 8 |
| blendif_parameters[64] | float[4*16] | 256 |
| blendif_boost_factors[16] | float[16] | 64 |
| raster_mask_source | dt_dev_operation_t (char[20]) | 20 |
| raster_mask_instance | int32 | 4 |
| raster_mask_id | dt_mask_id_t (int32) | 4 |
| raster_mask_invert | gboolean (int32) | 4 |

Python struct format (little-endian, matches
`helper/dt_ai_helper/styles.py::_BLENDOP_STRUCT`):
`"<IiIffIiIfIffffIII" + "f"*64 + "f"*16 + "20s" + "iii"` → 420 bytes,
asserted in `styles.py`.

**Default values**: `static dt_develop_blend_params_t _default_blendop_params`
in `src/develop/blend.c` (used by `dt_develop_blend_init_blend_parameters`,
which every op calls to seed its blend params when first enabled and the
user hasn't touched the blend-mode tab):

- `mask_mode = DEVELOP_MASK_DISABLED` (0) — **blending is off**; the
  module's output is used unblended at full strength. This is the state
  plan §12 scopes generated styles to ("masks/parametric blending in
  generated styles (blend params default only)").
- `blend_cst = DEVELOP_BLEND_CS_NONE` (0), `blend_mode =
  DEVELOP_BLEND_NORMAL2` (0x18), `blend_parameter = 0.0`, `opacity =
  100.0`, `mask_combine = DEVELOP_COMBINE_NORM_EXCL` (0 — `NORM|EXCL` are
  both 0x00), `mask_id = 0`, `blendif = 0`, `feathering_radius = 0.0`,
  `feathering_guide = DEVELOP_MASK_GUIDE_IN_AFTER_BLUR` (5),
  `blur_radius/contrast/brightness/details = 0.0`, `feather_version = 1`,
  `reserved = {0,0}`.
- `blendif_parameters`: `{0,0,1,1}` repeated for all 16 channel slots
  (each channel's filter range defaults to "fully open", i.e. no
  filtering).
- `blendif_boost_factors`: all `0.0`.
- `raster_mask_source = {0}` (empty/no raster mask), `raster_mask_instance
  = 0`, `raster_mask_id = INVALID_MASKID` (`#define INVALID_MASKID (-1)`,
  `src/common/darktable.h:168`), `raster_mask_invert = FALSE`.

This is exactly what `styles._default_blendop_params_bytes()` builds; it's
computed once at import time as `styles.DEFAULT_BLENDOP_PARAMS` and reused
for every emitted `<plugin>`, matching plan §7.4's "default `blendop_params`
to the standard defaults blob per blend version."

`blendop_version` in the emitted `<plugin>` is `BLENDOP_VERSION = 13`
(`DEVELOP_BLEND_VERSION` at this tag) for every entry — there's no
per-module blend-version variance to track.

## 3. Op params defaults (needed for `/style`'s recommendation-only input)

The task's `/style` contract (see §4 below) takes only a structured
recommendation, not the current edit state — so a recommendation that
says "raise exposure by 0.5 EV" needs a *base* value for every other field
in `dt_iop_exposure_params_t` to produce a valid, complete struct to
encode. `styles.DEFAULT_PARAMS` supplies that base, one dict per Tier-1
op, transcribed from each op's own `$DEFAULT:` introspection annotation in
`src/iop/<op>.c` @ release-4.6.0 — darktable's own struct-field-comment
convention (e.g. `float exposure; // $MIN: -18.0 $MAX: 18.0 $DEFAULT:
0.0`), not guessed. Every `DEFAULT_PARAMS[op]` dict was verified to
encode→decode round-trip byte-for-byte via its `params_codec` module (see
`test_styles.py` and the ad-hoc check run during development).

**`denoiseprofile` has no entry.** Its `a`/`b` per-channel
Poissonian-Gaussian noise-model fit coefficients and its `x`/`y`
wavelet-band correction curves are fit per-camera/per-ISO at runtime from
a noise-profile database (`dt_noiseprofile_*`) — there is no meaningful
static factory default (an all-zero fit is degenerate, not "off"). A
`denoiseprofile` recommendation is therefore always reported as skipped
with reason "no known default parameters ... requires a current-edit-state
base" unless/until a future worker threads the current `image_context`
into `/style` as an optional base-params source.

**`crop` has no `CONTROL_MAP` entries.** Its fields are edge-position
fractions (`cx`/`cy`/`cw`/`ch`) and an aspect-ratio pair, not the kind of
single named slider an LLM recommendation's `{"control": str, "value":
str}` shape naturally expresses — left unmapped by design rather than
guessing a geometry-parsing scheme; a `crop` recommendation always
produces a "no known default parameters" skip via the same defaults gate
described above (it's also absent from `DEFAULT_PARAMS`... actually it
*is* present, since `cx=cy=0, cw=ch=1, ratio_n=ratio_d=-1` — "no crop" —
is a perfectly good default; it just has no `CONTROL_MAP`, so any
`settings` entries under a `crop` recommendation always land as
unrecognized-control skips while the module itself is still emitted at
its default "no crop" state).

## 4. `/style` contract deviation from plan §5.2

Plan §5.2 literally specifies:

```
POST /style → {recommendation_id} → {file}
```

i.e. a `recommendation_id` referencing a prior job's stored structured
output. This worker's task spec instead specifies (and this is what's
implemented in `api.py::create_style`):

```
POST /style → {recommendation: {...}, name?} → {file, included_ops, skipped_ops, manual_steps}
```

Rationale for not implementing the `recommendation_id` form: nothing in
the currently-merged codebase stores a structured recommendation
server-side keyed by an id (the `/chat`/`/optimize`/job-result shapes
don't have one yet), so `recommendation_id` has no data source to resolve
against today. Taking the recommendation inline avoids inventing a second,
possibly-conflicting storage/lookup mechanism ahead of whoever builds
`/optimize`'s real pipeline. If a future worker adds recommendation
storage keyed by id, `/style` could gain a `recommendation_id` variant
alongside (not instead of) the inline one without breaking this shape.
Flagged here and in the PR description per
`documentation/agent-insights/002-conventions-for-subagents.md`'s "propose,
don't unilaterally change the contract" rule.

The richer response (`included_ops`/`skipped_ops`/`manual_steps`) matches
what the task spec asked for and what plan §7.4's "recommendations that
include non-encodable modules produce a style for the encodable subset + a
text note listing manual steps" requires — a bare `{file}` can't carry
that.

## 5. Outstanding / not covered

- No real darktable install available in this environment (same
  limitation as agent-insights 005/006) — the `.dtstyle` shape is verified
  against `src/common/styles.c`'s writer source, and internal round-trips
  are exhaustively tested, but no style built by `styles.py` has been
  imported into a real darktable to confirm it applies correctly. Manual
  task for a future worker: build a style via `/style`, `darktable.styles.import()`
  it, apply it to a test raw, and confirm the resulting edit matches what
  the encoded params should produce.
- `denoiseprofile` and `crop` styling is limited as described in §3 — both
  need a current-edit-state base (not just a recommendation) to be useful
  beyond their static defaults.
- Tier 2 ops have no codecs yet (out of this worker's scope; plan §7.3), so
  `translate_recommendation`/`build_style` will report them as "no params
  codec" skips until a future worker adds Tier 2 encoders — nothing in
  `styles.py` needs to change for that; the registry lookup already
  degrades cleanly.
