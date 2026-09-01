# 011 — Lua↔helper HTTP contract, as actually implemented

Written by W8 (`feat/packaging`), Phase 6. This is the authoritative
description of the contract between `lua/dt-ai-assistant.lua` and
`helper/dt_ai_helper/api.py` **as the merged code actually behaves** —
plan §5.2 is the design intent, this file is the as-built reality,
including every deviation the individual feature workers already noted in
their own PRs/insight files (004, 007, 009, 010). If this file and plan
§5.2 disagree, this file wins; update both together if you change the
contract again.

Transport: JSON over HTTP to `127.0.0.1:<port>` (port assigned at helper
startup, port 0 bind). Every request must carry
`Authorization: Bearer <token>` — **including `/health`**; there is no
unauthenticated route. A missing/wrong token gets a bare
`{"detail": "unauthorized"}` with status 401 from `main.BearerAuthMiddleware`,
before any route code runs.

## Routes

### `GET /health`
No body. Response:
```json
{"status": "ok", "version": "<dt_ai_helper.__version__>", "model_ready": true|false}
```
`model_ready` is true iff a preset is active and has non-empty `base_url`
and `model` (see `ConfigStore.model_ready`). There is no `model_ready`
check on the model actually being reachable — it only reflects local
config completeness.

### `GET /config`
No body. Response: `{"active": "<preset name>"|null, "presets": {<name>: {...}}}`.
Every preset dict has its `api_key` replaced with the literal string
`"***"` if it was non-empty (plan: "api_key redacted").

### `POST /config`
Body (`ModelPreset`):
```json
{"name": str, "base_url": str, "api_key": str|null, "model": str, "supports_vision": bool}
```
Upserts the preset by `name` into an **in-memory, non-persistent**
`ConfigStore` (nothing survives a helper restart — Lua re-sends the active
preset before every job, see `sync_active_preset()`). The first preset ever
upserted becomes active automatically; there is no separate
"select active preset" endpoint — `sync_active_preset()` just re-upserts
whichever preset is selected in the combobox on every Send/Optimize/Analyze,
and upserting an existing name does not change which preset is active
unless it's the first one. Response: same shape as `GET /config`.

### `POST /heartbeat`
No meaningful body. Resets `app.state.last_heartbeat`; the watchdog
self-exits the process ~10 minutes (`DEFAULT_HEARTBEAT_TIMEOUT`) after the
last heartbeat (or since start, if none ever arrives). Response:
`{"status": "ok"}`.

### `POST /chat` → `{"job_id": str}`
Body (`ChatRequest`):
```json
{"message": str, "history_id": str|null, "image_context": {...}|null}
```
Enqueues a `"chat"` job. `history_id` defaults server-side to `"default"`
if omitted — Lua always sends one keyed `"<image.id>:<clear-epoch>"` (see
`history_id_for()`), so the "Clear" button works by bumping a local epoch
counter rather than calling `/history/clear` (though that route exists too,
see below).

Job result (`GET /jobs/{id}` once `status == "done"`):
```json
{"answer": str, "style": null}
```
`/chat`'s `style` is **always** `null` — chat never builds a style, only
`/optimize` does (see deviation note below on `job.to_public_dict`).

### `POST /optimize` → `{"job_id": str}`
Body (`OptimizeRequest`):
```json
{"image_context": {...}|null, "preview_path": str}
```
`preview_path` must already exist on disk (a JPEG exported by Lua at the
configured preview max edge) — the job errors immediately
(`PreviewNotFoundError`) if it doesn't, without ever reaching the LLM.

Job result:
```json
{
  "answer": str,
  "style": {"file": str, "summary": str} | null,
  "recommendation": {
    "assessment": str,
    "recommendations": [
      {"module": str, "why": str, "settings": [{"control": str, "value": str}], "priority": int}
    ]
  }
}
```
`style` is only present when at least one recommended module was actually
encodable into a `.dtstyle` (`included_ops` non-empty) — a recommendation
naming only unencodable modules (e.g. only `denoiseprofile`) still returns
a full `answer`/`recommendation` with `style: null`. The style, when
present, is built **server-side** by `/optimize`'s own job handler calling
the same `_style_from_recommendation()` helper `/style` uses — Lua's
"Apply style" button reads `job.style.file` directly from the `/optimize`
job result; it never calls `/style` itself for the Optimize flow.

### `POST /vision` → `{"job_id": str}`
Body (`VisionRequest`) — **note the `allow_upload` field, which is not in
plan §5.2's literal contract**:
```json
{"message": str|null, "image_context": {...}|null, "preview_path": str, "allow_upload": bool}
```
`allow_upload` must be Lua's `allow_cloud_upload` preference value, sent on
every call (see agent-insights 010 for why: the privacy gate has to be
evaluated per-request against whichever preset is active, and `ConfigStore`
has no other channel for this user-level consent toggle — it's not part of
`ModelPreset`). **This field was being omitted by the Lua front-end until
this PR** (see the fix in this same branch) — omitting it meant
`allow_upload` defaulted to `false` server-side and any cloud vision-capable
preset was refused even with the local "allow image upload" preference on
and the local pre-check in `do_analyze()` passing.

Refusal ordering, checked in this order before any image bytes are read or
any LLM client is built:
1. No active/ready preset → `NoActivePresetError` (job `error`, not a crash).
2. Active preset's `supports_vision` is false → `VisionNotSupportedError`.
3. `guard_vision_upload(base_url=preset.base_url, allow_upload=...)` fails
   (non-local endpoint, `allow_upload` false) → `llm.VisionNotAllowed`,
   whose message is surfaced verbatim as the job's `error` field, e.g.
   `"refusing to send an image to a non-local endpoint ('api.openai.com')
   without allow_upload consent"`.
4. `preview_path` missing/unreadable → `PreviewNotFoundError`.

Job result:
```json
{"answer": str, "style": null, "description": str}
```
`description` is pass 1's raw "what does this image look like" text
(before pass 2 maps it onto module suggestions) — not in plan §5.2, kept
for transparency/future UI use; Lua currently ignores it. `style` is always
`null` — vision never builds a style.

### `GET /jobs/{id}`
No body. 404 (`{"detail": "job not found"}`) if the id is unknown or has
aged out (only the most recent 20 jobs across all kinds are kept, LRU by
submission order — `jobs.MAX_JOBS`). Otherwise:
```json
{"id": str, "status": "queued"|"running"|"done"|"error", ...}
```
When `status == "done"`, the job's result dict (one of the three shapes
above, depending on kind) is merged directly into the top level — there is
no `result` wrapper key. When `status == "error"`, an `"error": str` field
is added (the exception's `str()`, verbatim — every custom exception in
`api.py` is written to already be a clean, user-facing message, so `jobs.py`
does no extra formatting).

### `POST /history/clear`
Body: `{"history_id": str}`. Clears one server-side chat history. Response:
`{"status": "ok"}`. **Lua does not currently call this route** — the
"Clear" transcript button instead bumps a local per-image "epoch" counter
(`state.history_epoch[image.id]`) that changes what `history_id_for()`
computes, which orphans the old history server-side (it just ages out via
`jobs`... actually via `ChatHistoryStore`, which has no eviction of its own
beyond `clear()` — old `history_id` entries accumulate in memory for the
life of the helper process, bounded only by the helper's own lifetime via
the heartbeat self-exit). `/history/clear` exists and works if a future
worker wants Lua's Clear button to free that memory immediately instead.

### `POST /style` → `{file, included_ops, skipped_ops, manual_steps}`
Body (`StyleRequest`) — **deviates from plan §5.2's
`{recommendation_id} -> {file}`**:
```json
{"recommendation": {"recommendations": [...]}, "name": str|null}
```
Takes the structured recommendation **inline**, not a `recommendation_id`
(nothing in the codebase stores a recommendation server-side keyed by an
id — see agent-insights 007 §4 for the full rationale). `name` defaults to
`"ai-assistant/style-<unix-timestamp>"`. Response:
```json
{
  "file": str,
  "included_ops": [str, ...],
  "skipped_ops": [{"module": str, "control": str|null, "reason": str}, ...],
  "manual_steps": [str, ...]
}
```
`manual_steps` is human-readable prose generated from `skipped_ops`, one
line per skip — this is what plan §7.4's "text note listing manual steps"
requirement is rendered as. This is a **synchronous** route (no job/poll)
— style building is fast and CPU-only (no network call), unlike chat/
optimize/vision.

## `image_context` shape, as actually assembled

Lua sends a **partial** context (built by `build_image_context()` in the
Lua file — confusingly the same name as `context.build_image_context()` in
Python, which does something different: the Python one enriches, the Lua
one collects):
```json
{"filepath": str, "sidecar": str|null, "exif": {...}, "change_timestamp": number|string|null}
```
The helper's `context.build_image_context()` (in `context.py`) enriches
this into the full plan §5.2 shape:
```json
{
  "filepath": str, "sidecar": str|null, "exif": {...},
  "history_source": "xmp" | "db" | "none",
  "enabled_modules": [
    {"op": str, "label": str, "multi_name": str, "modversion": int,
     "params_decoded": {...} | null, "note": str | undefined}
  ],
  "iop_order": [str, ...],
  "histogram": {...}   // only present if Lua already put one in raw_context; nothing does today
}
```
Per agent-insights 004: **Lua never computes or sends `history_source`
itself** — it has no portable `stat()` call, so it just sends `sidecar` and
`change_timestamp` (from `dt_lua_image_t.change_timestamp`) and lets
`context.resolve_edit_state()` (Python, trivial `os.path.getmtime`) decide
xmp-vs-db-vs-empty. The preference order actually implemented: fresh
parseable sidecar → `library.db` (only if a caller passes `db_path`/
`image_id` into `resolve_edit_state`'s kwargs — **`run_chat_job`/
`run_optimize_job`/`run_vision_job` all read these from
`raw_image_context.get("db_path")`/`.get("image_id")`, but Lua never sends
either key today**, so the db fallback is effectively dead code until a
future worker wires it up from the Lua side) → stale-but-parseable sidecar
→ an explicit empty edit state (`history_source: "none"`, empty lists).
This function never raises.

## Job-kind → handler registration

`main.create_app()` registers three job kinds by name:
`"chat"` → `api.run_chat_job`, `"optimize"` → `api.run_optimize_job`,
`"vision"` → `api.run_vision_job`, each wrapped in a closure supplying the
owning `FastAPI` app (job handlers otherwise only see their `payload` dict
per `jobs.JobManager`'s contract). There is no `"style"` job kind —
`/style` is synchronous, not queued.

## Error semantics, uniformly

Every custom exception raised inside a job handler
(`NoActivePresetError`, `PreviewNotFoundError`, `VisionNotSupportedError`,
`llm.VisionNotAllowed`, a wrapped `RuntimeError` for any `llm.LLMError`) is
designed to already be a complete, user-facing sentence.
`jobs.JobManager._worker_loop` catches `Exception` broadly and stores
`str(exc)` as the job's `error` field with no additional wrapping or
prefixing — so a job's `error` string in `GET /jobs/{id}` is always exactly
what the raising code wrote, never a generic "internal error" or a
traceback. Synchronous routes (`/config`, `/style`, `/history/clear`) rely
on FastAPI/pydantic's normal validation-error responses (422) for malformed
bodies; there is no bespoke error shape for those.

## Deviations from plan §5.2, collected in one place

1. `/vision` request gains `allow_upload: bool` (agent-insights 010; fixed
   on the Lua side in this same PR — see task 1 above).
2. `/style` takes an inline `recommendation` object instead of a
   `recommendation_id`, and returns `{file, included_ops, skipped_ops,
   manual_steps}` instead of bare `{file}` (agent-insights 007 §4).
3. `/optimize`'s job result carries the full structured `recommendation`
   object alongside `answer`/`style`, not just `answer`/`style` (needed so
   `/style` semantics — and any future "regenerate style from last
   recommendation" UI — have something to work from).
4. `/vision`'s job result carries an extra `description` field (pass 1's
   raw description; agent-insights 010).
5. `POST /history/clear` exists as an explicit route keyed by `history_id`,
   which plan §5.2 does not mention at all (the plan has no history-clearing
   endpoint) — added because Lua's per-image chat history needs some way to
   be reset, and a `clear` flag on `ChatRequest` would conflate "clear" with
   "send a message" in one request shape. Currently unused by Lua (see
   above), which instead reuses `history_id` epoch-bumping — a legitimate
   alternative the helper also has to keep supporting.
