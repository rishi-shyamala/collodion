# 010 — Optimize/Vision: histogram rule tags, style-from-job, and vision privacy gate

Written by W6 (branch `feat/optimize-vision`) implementing plan Phases 3-4
(`darktableaiassistantplan.md` §5.2/§5.5/§6).

## Histogram stats are display-referred approximations, not scene-linear

`histogram.py` computes everything from the *exported preview JPEG*, which
is already sRGB-encoded and gamma-corrected. Every stat (percentiles,
clipping %, dynamic-range score, gray-world white-balance ratios, the
shadow noise proxy) is a heuristic for prompting an LLM, not a photometric
measurement of the scene. This is stated in the module docstring and in
the optimize system prompt itself (so the LLM doesn't over-trust the
numbers), per plan §6's explicit "document stats are display-referred
approximations" instruction.

## Rule-tag vocabulary implemented

`histogram.derive_issue_tags()` produces (in this priority order, deduped):
`underexposed`, `overexposed`, `highlights_clipped`, `shadows_clipped`,
`low_contrast`, `flat_midtones`, `color_cast_red`/`color_cast_blue`/
`color_cast_cyan`/`color_cast_yellow`, `low_saturation`, `high_iso_noise`
(gated on EXIF ISO + a noise proxy, not ISO alone), `no_denoise_enabled`
(only fires when ISO is high *and* no denoise-family op is already
enabled), `no_sharpening_enabled` (only when contrast/midtones are flagged
*and* no sharpen-family op is enabled), `long_exposure_hot_pixels_check`
(EXIF exposure >= 1s), `ultra_wide_lens_correction_check` (EXIF focal
length <= 20mm and `lens` isn't already enabled).

Thresholds live as module-level constants in `histogram.py` (e.g.
`UNDEREXPOSED_MEAN_LUMA`, `COLOR_CAST_RATIO_THRESHOLD`) — they're
heuristics tuned against the synthetic fixtures in `test_histogram.py`,
not derived from any darktable source. A future worker tuning these
against real-world images should adjust the constants, not the rule
structure.

## `optimize_retrieval_query` needs its own phrase map, not just the tags

Feeding raw underscored tags like `highlights_clipped` straight into
`rag.get_retriever()` works poorly — BM25 + `rag.py`'s synonym map is keyed
on words a *photographer* types, not internal tag identifiers. Added a
small `_ISSUE_TAG_QUERY_TERMS` dict in `prompts.py` translating each tag to
a short natural-language phrase (e.g. `highlights_clipped` -> "highlights
clipped blown out reconstruction filmic rolloff") before handing the query
to the retriever. This is a second, Optimize-specific vocabulary layered
on top of (not a replacement for) `rag.py`'s own `SYNONYMS` map — worth
keeping in sync if new tags are added to the rule layer.

## `/optimize` builds its style server-side, reusing `/style`'s pipeline

Per the orchestration log's integration note from W7 (PR #5): "the
optimize job handler should call styles internally and return `style.file`
in the job result" because Lua's Apply-style button expects it there. To
avoid duplicating `/style`'s translate → build → write sequence,
`api.py` now has a private `_style_from_recommendation()` helper extracted
from `/style`'s route body; both `/style` and `run_optimize_job` call it.
This is a refactor of the existing `/style` route (same external response
shape, verified against `tests/test_styles.py`'s existing endpoint tests
still passing) rather than a new file — flagging it since `/style`
strictly belongs to W7's PR #5, not this one.

`run_optimize_job` only attaches a `style` object to the job result when
at least one recommended module actually got encoded (`included_ops`
non-empty); a recommendation whose modules are all unencodable (e.g. an
LLM recommending only `denoiseprofile`, which has no static default
params — see `styles.py`'s own note) still returns a full
`recommendation` + rendered `answer`, just with `style: null`.

## `/vision`'s privacy gate is checked *before* touching the filesystem or building a client

`run_vision_job` calls `llm.guard_vision_upload(base_url=preset.base_url,
allow_upload=...)` immediately after the `supports_vision` check — before
reading `preview_path` off disk, before constructing an `OpenAIChatClient`.
This matches plan §5.4's framing ("never send the image unless...") as a
precondition to check first, not a step to unwind after doing other work.
A refused request surfaces the exact message `llm.VisionNotAllowed`
already formats (e.g. "refusing to send an image to a non-local endpoint
('api.openai.com') without allow_upload consent") as the job's `error`
field — no wrapping needed since `VisionNotAllowed` is already a clean,
user-facing `RuntimeError` subclass and `jobs.JobManager` stores
`str(exc)` verbatim.

## Deviations from the literal plan §5.2 contract (both noted in the PR body too)

1. **`POST /vision` request gains `allow_upload: bool`.** The literal
   contract is `{message?, image_context?, preview_path} -> {job_id}`.
   The privacy gate has to be evaluated per-request against whichever
   preset is active, and there's no other channel today for Lua's
   "allow image upload to cloud endpoints" preference (plan §5.1) to reach
   this request — `ConfigStore`/`ModelPreset` only carries a per-endpoint
   *capability* flag (`supports_vision`), not this user-level *consent*
   toggle. Lua should send its stored pref value on every `/vision` call.
2. **`main.py` touched outside strict per-worker file ownership.** Job
   kind registration (`app.state.job_manager.register_handler(...)`) only
   happens in `main.create_app`, following the existing `"chat"` kind's
   pattern — there's no other place to wire `"optimize"`/`"vision"` job
   dispatch without changing `jobs.JobManager`'s contract (which this
   worker was told not to touch). The diff is two small closures mirroring
   the existing `_run_chat_job` one; nothing else in `main.py` changed.

## Vision's job result carries an extra `description` field

Not in the literal plan §5.2 shape, but harmless and useful: pass 1's raw
description (before pass 2 maps it onto module suggestions) is returned
as `job.description` alongside `answer`/`style`, purely for transparency /
future UI use (e.g. showing "here's what the model saw" separately from
the recommendation). Lua can ignore it.
