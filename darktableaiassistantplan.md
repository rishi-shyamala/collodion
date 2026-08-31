# darktable AI Edit Assistant — Project & Implementation Plan

**Working name:** `dt-ai-assistant`
**Audience for this document:** an LLM coding agent (or human developer) building the plugin end-to-end. It contains the architecture, hard constraints of the darktable Lua API, component contracts, a phased implementation plan with acceptance criteria, and the content spec for the RAG module library.

---

## 1. Product summary

A darktable plugin that adds an AI assistant panel to the darkroom/lighttable sidebar. The user can:

1. **Chat** in a text box with an LLM about how to achieve a desired edit ("make this look like golden hour", "why is the sky blown out?").
2. Have the assistant **see the current edit state**: which processing modules are enabled on the current image and (for a curated set of modules) their parameter values.
3. Run **Optimize**: a one-click analysis of the image's histogram + EXIF/metadata that returns a recommended, ordered list of modules and settings.
4. Run **Vision analysis**: send a downscaled preview of the image to a vision-capable model, which proposes edits based on what the image actually looks like.
5. **Swap LLM backends freely** — any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, Ollama, LM Studio, vLLM, etc.) configured by base URL + model name + API key.
6. Get answers grounded in a bundled **plain-text RAG library** describing every darktable module, its purpose, key sliders, and before/after visual effect — so answers reference real module names and real slider names, not hallucinated ones.
7. Optionally **apply a recommendation**: the assistant can emit a darktable style (`.dtstyle`) for a curated set of modules, which the plugin imports and the user applies with one click.

Decisions already made by the product owner:

- **Architecture:** Lua front-end inside darktable + local Python helper service (no darktable fork/recompile).
- **LLM backend:** OpenAI-compatible API abstraction as the single provider interface (covers cloud and local).
- **Edit application:** recommend in chat, plus optional apply-via-styles. No direct history-stack writing.
- **Platforms:** Linux, Windows, macOS from day one.
- Cloud vision is acceptable, but everything must also work with a local OpenAI-compatible server (e.g., Ollama), so privacy-sensitive users can stay fully local.

---

## 2. Hard constraints (verified against darktable docs/community — design around these)

These are load-bearing facts. Do not "improve" the design in ways that violate them.

1. **The Lua API cannot read or write the darkroom history stack.** There is no Lua access to enabled modules or their parameters on an image. Confirmed by darktable contributors. Therefore module state must be obtained by **parsing the image's XMP sidecar** (path available as `image.sidecar` on `dt_lua_image_t`) or, as a fallback, reading `library.db` (SQLite, read-only, with lock handling).
2. **XMP sidecars hold the history stack** as `darktable:history` entries: one entry per history item with `darktable:operation` (module internal name), `darktable:enabled`, `darktable:modversion`, `darktable:params` (compressed blob, `gz`-prefixed base64 of the module's C params struct), plus `darktable:multi_name`/`multi_priority` for module instances, and `darktable:iop_order_list`.
3. **Decoding `params` into human-readable slider values requires per-module struct definitions** that mirror darktable's C structs and are versioned by `modversion`. This is feasible but per-module work; the plan curates a priority list (§7.3) rather than attempting all ~90 modules.
4. **XMP freshness:** darktable writes sidecars on edit only if the preference "write sidecar file for each image" is set to "on import"/"after edit" (default writes after edits). The Lua front-end should surface a warning if sidecar is missing/stale, and can trigger a flush via the GUI action API (`darktable.gui.action("lib/copy_history/write sidecar files", ...)`) on supported versions; the helper additionally falls back to `library.db`. Never assume the XMP is current without checking mtime vs. `image.change_timestamp`.
5. **Lua CAN:** build sidebar UI (`darktable.new_widget` + `darktable.register_lib` — box, label, entry, button, combobox, text_view, separator, section_label), get the acted-on/selected image (`darktable.gui.action_images`), read image EXIF attributes (`exif_iso`, `exif_aperture`, `exif_exposure`, `exif_focal_length`, `exif_maker`, `exif_model`), export images through `darktable.modules.format` exporters, import/apply styles (`darktable.styles.import(filename)`, `darktable.styles.apply(style, image)`), run external processes (`darktable.control.execute`), and store settings (`darktable.preferences`).
6. **Lua is single-threaded within darktable and long blocking calls freeze the UI.** All LLM/network work must happen in the Python helper; the Lua side must poll or use short non-blocking requests. darktable's bundled Lua has no HTTP stack — shell out to `curl` via `darktable.control.execute`, or communicate via files. `dt.control.execute` blocks the Lua thread but runs inside a coroutine-friendly control layer; keep calls short and use the job/polling pattern in §5.3.
7. **A registered lib module appears in the left or right panel** depending on `container` argument; it is expandable/collapsible like native modules. Lua widgets are limited (no rich text, no streaming text), so the chat transcript renders in a `text_view` (read-only multi-line) or via incremental label updates — design the UX within that.
8. **Style application works from Lua** and is the sanctioned "apply edits" path. Generating a `.dtstyle` file requires emitting the same versioned params blobs as XMP; the helper reuses the same struct codecs (encode direction) for the curated module set only.

---

## 3. Architecture overview

```
┌────────────────────────────────────────────────────────────┐
│ darktable                                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ dt-ai-assistant.lua  (sidebar lib module)            │  │
│  │  - chat UI (entry, text_view, buttons, model picker) │  │
│  │  - collects: image path, sidecar path, EXIF, prefs   │  │
│  │  - exports downscaled JPEG preview on demand         │  │
│  │  - talks to helper via HTTP on 127.0.0.1:<port>      │  │
│  │    using curl through dt.control.execute             │  │
│  │  - imports & applies returned .dtstyle files         │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                       │ localhost HTTP (JSON), token-authed
                       ▼
┌────────────────────────────────────────────────────────────┐
│ dt-ai-helper  (Python 3.10+, FastAPI + uvicorn, localhost) │
│  ├─ /chat        conversational endpoint (job-based)       │
│  ├─ /optimize    histogram+metadata recommendation         │
│  ├─ /vision     preview-image analysis                     │
│  ├─ /style       build .dtstyle from a recommendation      │
│  ├─ /health /config /models                                │
│  ├─ xmp.py      sidecar parser + params codecs (§7)        │
│  ├─ dbfallback.py  read-only library.db reader             │
│  ├─ histogram.py   numpy/Pillow histogram + stats          │
│  ├─ rag.py      plain-text module library retrieval (§8)   │
│  ├─ llm.py      OpenAI-compatible client (swappable)       │
│  └─ styles.py   .dtstyle XML emitter (curated modules)     │
│  data/                                                     │
│  └─ module_library/*.md   ← the RAG corpus (bundled)       │
└────────────────────────────────────────────────────────────┘
                       │ HTTPS (only when user configures a
                       ▼         cloud base URL)
            Any OpenAI-compatible endpoint
     (OpenAI / OpenRouter / Groq / Ollama / LM Studio / vLLM)
```

**Why HTTP over localhost rather than pipes/files:** cross-platform (Windows lacks decent named-pipe ergonomics from Lua), debuggable with curl, and the job-polling pattern maps naturally onto darktable's no-long-blocking constraint. Bind strictly to `127.0.0.1`, generate a random bearer token at helper startup, write it to a mode-600 token file that the Lua script reads and sends on every request.

**Helper lifecycle:** the Lua script launches the helper on darktable start (`dt.control.execute` with platform-appropriate detach), health-checks `/health`, and shows status in the panel. The helper self-terminates after N minutes without a heartbeat so it never outlives darktable. Port is chosen by the helper (bind port 0), written to the token file alongside the token.

---

## 4. Repository layout

```
dt-ai-assistant/
├── README.md
├── LICENSE                     (GPL-3.0 — required: links against darktable's Lua API ecosystem conventions)
├── lua/
│   └── dt-ai-assistant.lua     single-file Lua front-end
├── helper/
│   ├── pyproject.toml          (fastapi, uvicorn, pillow, numpy, httpx, lxml or stdlib ElementTree)
│   ├── dt_ai_helper/
│   │   ├── main.py             app factory, auth middleware, lifecycle/heartbeat
│   │   ├── api.py              route handlers, job manager
│   │   ├── llm.py              OpenAIChatClient (base_url, api_key, model, vision flag)
│   │   ├── xmp.py              sidecar parse: history entries, iop order, instances
│   │   ├── params_codec/
│   │   │   ├── registry.py     op name+modversion → codec
│   │   │   ├── exposure.py     …one file per curated module (decode + encode)
│   │   │   └── ...
│   │   ├── dbfallback.py       sqlite3 read-only fallback
│   │   ├── histogram.py        stats from exported preview JPEG
│   │   ├── rag.py              corpus load, chunk, BM25 (rank-bm25) retrieval
│   │   ├── styles.py           .dtstyle XML emitter
│   │   └── prompts.py          system prompts for chat / optimize / vision
│   └── data/
│       └── module_library/     ~90 markdown files, one per module (§8)
├── scripts/
│   ├── install.sh / install.ps1
│   └── build_library.py        optional: regenerate/validate the RAG corpus
└── tests/
    ├── fixtures/               sample XMPs (multiple dt versions), sample JPEG previews
    ├── test_xmp.py  test_codecs.py  test_histogram.py  test_rag.py  test_styles.py
    └── test_api.py
```

---

## 5. Component specifications

### 5.1 Lua front-end (`lua/dt-ai-assistant.lua`)

Register with `darktable.register_lib("ai_assistant", "AI assistant", true, false, {[dt.gui.views.darkroom] = {"DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100}, [dt.gui.views.lighttable] = {"DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100}}, widget)`.

Widget tree (all `darktable.new_widget`):

- `section_label` "AI assistant" status line (helper: running/stopped; model name)
- `text_view` (read-only, ~12 lines) — chat transcript, plain text, prefixed `You:` / `AI:`
- `entry` — user input; Enter or "Send" button submits
- `box(horizontal)`: **Send**, **Optimize**, **Analyze image** (vision), **Apply style** (enabled only when the last response carried a style), **Clear**
- `combobox` — model preset picker (named presets from prefs; e.g. "gpt-5.2", "ollama/qwen3-vl", "openrouter/llama-4")
- `check_button` — "include my current edit state in context" (default on)

Preferences (via `darktable.preferences.register`, shown in darktable's Lua options tab): helper path, python path, up to N model presets each with `name / base_url / api_key / model / supports_vision`, preview max edge (default 1024 px), "allow image upload to cloud endpoints" toggle, request timeout.

Responsibilities:

1. On darktable start: launch helper, read token file, health-check.
2. On Send/Optimize/Analyze: gather context — `image = dt.gui.action_images[1]`; EXIF fields; sidecar path; rating/tags; for vision/optimize, export preview via the JPEG format exporter at configured max edge to a temp dir; POST job to helper; poll `/jobs/<id>` every ~700 ms with `dt.control.execute` curl until done (show `…` progress in transcript); append answer.
3. XMP freshness check: compare sidecar mtime against `image.change_timestamp`; if stale, attempt `darktable.gui.action("lib/copy_history/write sidecar files", ...)` guarded by `pcall` (API varies by dt version), then tell the helper which source to trust (`xmp` vs `db`).
4. Apply style: response includes `style_file` path → `local s = darktable.styles.import(path)` → `darktable.styles.apply(s, image)`; name styles `ai-assistant/<slug>-<timestamp>` so they're identifiable and deletable.
5. All curl invocations: `--max-time`, `-s`, write JSON body to temp file (avoids shell-quoting bugs on Windows), `-H "Authorization: Bearer <token>"`.

**darktable version target:** 4.6+ (Lua API 9.x); guard version-dependent calls with `darktable.configuration.api_version_major/minor` checks and degrade gracefully.

### 5.2 Helper API contract (all JSON; all endpoints require bearer token)

```
GET  /health          → {status, version, model_ready}
GET  /config          → current provider config (api_key redacted)
POST /config          → set/select model preset {name, base_url, api_key, model, supports_vision}
POST /chat            → {message, history_id?, image_context?} → {job_id}
POST /optimize        → {image_context, preview_path} → {job_id}
POST /vision          → {message?, image_context?, preview_path} → {job_id}
GET  /jobs/{id}       → {status: queued|running|done|error, answer?, style?: {file, summary}, error?}
POST /style           → {recommendation_id} → {file}   (builds .dtstyle from a prior structured recommendation)
POST /heartbeat       → keepalive from Lua (helper exits ~10 min after last beat)
```

`image_context` (built partly by Lua, enriched by helper):

```json
{
  "filepath": "...", "sidecar": "...",
  "exif": {"iso": 800, "aperture": 2.8, "exposure": 0.008, "focal_length": 35,
            "maker": "FUJIFILM", "model": "X-T5", "datetime": "..."},
  "history_source": "xmp",
  "enabled_modules": [
    {"op": "exposure", "label": "exposure", "multi_name": "", "modversion": 6,
     "params_decoded": {"exposure_ev": 0.65, "black_level": -0.0002}, "raw_params": "gz..."},
    {"op": "filmicrgb", "params_decoded": null, "note": "decoder not available for modversion 5"}
  ],
  "iop_order": ["rawprepare", "...", "filmicrgb"],
  "histogram": {"mean": [..], "clipped_black_pct": 0.4, "clipped_white_pct": 2.1,
                 "luma_percentiles": {"p1":..,"p50":..,"p99":..}, "per_channel": {...}}
}
```

### 5.3 Job model

In-process queue (`asyncio` tasks), one worker; LLM calls streamed internally but the job result is returned whole (Lua text_view can't stream usefully). Keep last 20 jobs. Chat history kept server-side per `history_id` (per-image, reset on Clear), trimmed to fit a configurable context budget.

### 5.4 LLM client (`llm.py`)

Single class speaking the OpenAI Chat Completions API (`POST {base_url}/chat/completions`) — this is the swap point; changing models = changing `{base_url, model, api_key}`. Vision messages use the standard `image_url` content-part with a base64 data URL of the preview JPEG. Support `temperature`, `max_tokens`, retry-with-backoff on 429/5xx, and a `strict_json` mode (uses `response_format: json_object` when the endpoint supports it, otherwise a fenced-JSON-extraction fallback) for Optimize's structured output. **Never send the image unless the request is a vision request AND (endpoint is localhost OR the "allow image upload" pref is on).**

### 5.5 Prompting (`prompts.py`)

- **Chat system prompt:** "You are an assistant embedded in darktable `<version>` … Only reference modules and controls that appear in the provided MODULE LIBRARY excerpts or CURRENT EDIT STATE. Give steps as: module name → section → slider → suggested value/range. Prefer scene-referred workflow (filmic rgb/sigmoid, color balance rgb, tone equalizer) unless the edit state shows display-referred modules in use." Context blocks appended: `CURRENT EDIT STATE` (serialized image_context), `MODULE LIBRARY` (top-k RAG chunks for the user's message).
- **Optimize prompt:** input = histogram stats + EXIF + enabled modules; retrieval query synthesized from detected issues (e.g., "highlights clipped 2.1% → highlight reconstruction, filmic white relative exposure"). Output contract = strict JSON: `{"assessment": str, "recommendations": [{"module": op_name, "why": str, "settings": [{"control": str, "value": str}], "priority": 1}]}` — rendered as readable text for the transcript and kept structured for `/style`.
- **Vision prompt:** asks the model to describe subject, light, color casts, composition issues, then map each observation to module suggestions, constrained by the same library excerpts. Runs with the RAG block for whatever issues the model names (two-pass: pass 1 describe, pass 2 recommend with retrieval — keeps retrieval relevant).

---

## 6. Optimize feature (histogram + metadata)

Computed in `histogram.py` from the exported preview JPEG (sRGB, so document that stats are display-referred approximations):

- per-channel and luma histograms (256 bins); % pixels within 1% of black / white (clipping); percentiles p1/p5/p50/p95/p99; mean saturation (HSV); a simple dynamic-range utilization score; white-balance hint via gray-world R/G/B means ratio; noise proxy from high-frequency stddev in shadows vs. ISO.

Rule layer (deterministic, before the LLM) tags issues: `underexposed`, `highlights_clipped`, `low_contrast`, `flat_midtones`, `color_cast_blue/…`, `high_iso_noise`, `no_sharpening_enabled`, etc. These tags + raw stats + EXIF go to the LLM, which writes the human recommendation. Deterministic tags make output stable across models and give the RAG retriever good queries. High ISO + `denoise (profiled)` absent → recommend it; long exposure → hot-pixels; ultra-wide focal length → lens correction check, and so on.

---

## 7. Reading module state (XMP parsing + params codecs)

### 7.1 `xmp.py`

Parse the sidecar with ElementTree (namespaces: `xmp`, `darktable`, `exif`, `dc`). Extract: `darktable:history` sequence (each: `operation`, `enabled`, `modversion`, `params`, `multi_name`, `multi_priority`, `blendop_params`, `blendop_version`), `darktable:iop_order_list`, `darktable:history_end` (items after history_end are undone — exclude), auto-apply defaults presence. Collapse the stack: last entry per (operation, multi_priority) wins. Handle both compressed (`gz` + base64, zlib after a leading repetition-count byte scheme — darktable uses `gz` followed by base64 of `deflate`d data; verify against fixtures) and plain hex params.

### 7.2 Fallback `dbfallback.py`

If sidecar missing/stale and Lua couldn't flush it: open `~/.config/darktable/library.db` (path from Lua's `darktable.configuration.config_dir`) read-only (`file:...?mode=ro&immutable=0`), query `history` + `images` tables. Copy to temp first if locked. Same output shape as xmp.py.

### 7.3 Params codecs (`params_codec/`)

Each codec = Python `struct` layout(s) keyed by `modversion`, decode → named dict with units, encode ← dict (encode used only by styles). **Curated priority list (build in this order):**

Tier 1: `exposure`, `filmicrgb`, `sigmoid`, `colorbalancergb`, `toneequal`, `highlights`, `temperature` (white balance), `sharpen`/`diffuse`, `denoiseprofile`, `crop`/`clip`.
Tier 2: `channelmixerrgb` (color calibration), `colorzones`, `bilat` (local contrast), `lens`, `ashift` (rotate & perspective), `vignette`, `graduatednd`, `velvia`, `lowpass`, `retouch` (presence only).

Unknown module or modversion → report `{op, enabled, decoded: null}`; the assistant still knows the module is on, which is most of the value. **Ground truth for layouts:** the corresponding `src/iop/<op>.c` `dt_iop_<op>_params_t` structs in the darktable source at the targeted release tag; pin fixtures per dt version and add a CI test that decodes known XMPs to known values.

### 7.4 Styles emitter (`styles.py`)

`.dtstyle` = XML (`<darktable_style version="1.0">` with `<info><name>…` and `<style><plugin>` entries carrying num/module(modversion)/operation/op_params/blendop_params/enabled/multi_name/multi_priority). Emit only ops with a working **encoder**; default `blendop_params` to the standard defaults blob per blend version (capture from fixtures). Recommendations that include non-encodable modules produce a style for the encodable subset + a text note listing manual steps. Validate every emitted style by round-trip decoding before returning it.

---

## 8. RAG module library (`data/module_library/`)

One markdown file per darktable processing module, plain text, ~300–600 words each, **written for retrieval and grounding rather than as documentation prose**. Template:

```markdown
# filmic rgb (filmicrgb)
group: tone | scene-referred | typical position: late tone mapping
purpose: Compresses scene dynamic range to display range with controllable
contrast; the main tone-mapping module of the scene-referred workflow.
use_when: image looks flat/dark after exposure; highlights need rolloff;
replacing base curve. do_not_combine: base curve, sigmoid (choose one).
key_controls:
- white relative exposure (scene tab): sets what becomes pure white.
  Raise → recover highlight detail; typical +2.5 to +5 EV.
- black relative exposure: sets what becomes black. Lower → deeper blacks…
- contrast (look tab): 1.0–1.8; higher = punchier midtones…
visual_effect: BEFORE: flat, low contrast, washed highlights. AFTER:
compressed highlights with smooth rolloff, deeper blacks, midtone contrast…
pitfalls: over-raising white rel. exposure grays highlights; latitude too
wide causes halos with high contrast…
pairs_with: exposure (set middle-gray first), color balance rgb, tone equalizer
```

Frontmatter-style first lines make op-name and synonyms exact-match findable. Retrieval: chunk = whole file (they're small), BM25 (`rank-bm25`) over lowercased text + a synonym map ("wb"→temperature, "clarity"→local contrast/diffuse, "curves"→tone curve/rgb curve, "hdr look"→filmic/tone equalizer). Top-k = 4 files per query, injected verbatim. No embeddings/vector DB in v1 — corpus is ~40k words, BM25 + synonyms is sufficient, zero extra deps, fully offline. Leave `rag.py` behind an interface so an embedding retriever can be swapped in later.

**Corpus production:** write from the darktable 4.6/5.x user manual's module reference (docs.darktable.org, GPL-compatible; attribute in README), rewritten into the template — the agent should generate all Tier 1+2 module files with full `key_controls`, and stub the long tail (purpose + use_when only) in v1. `scripts/build_library.py` validates template conformance (required sections present, op name matches a known op list).

---

## 9. Implementation phases

### Phase 0 — Skeleton & plumbing (goal: round trip)
- Repo scaffold, pyproject, helper with `/health`, token file, port-0 bind, heartbeat self-exit.
- Lua lib module registers, panel renders, launches helper, shows green status.
- Chat echo (no LLM): Send → helper → canned reply → transcript.
- **Accept:** panel visible in darkroom on Linux+Windows+macOS; helper starts/stops with darktable; echo round trip < 1 s.

### Phase 1 — LLM chat + RAG
- `llm.py` (OpenAI-compatible, presets, retries), `rag.py` + Tier 1 corpus files, chat prompt assembly, job queue + Lua polling, per-image history, model preset combobox.
- **Accept:** with both a cloud endpoint and a local Ollama endpoint: "how do I make the sky more dramatic?" returns steps naming real modules/sliders drawn from the library; swapping presets requires no restart.

### Phase 2 — Edit-state awareness
- `xmp.py`, freshness check + GUI-action flush attempt, `dbfallback.py`, codecs for Tier 1 modules, `image_context` assembly, "include edit state" toggle.
- **Accept:** fixture XMPs from dt 4.6 and 5.x decode correctly in CI; in-app, asking "what have I already done to this photo?" lists the enabled modules with decoded exposure/filmic values; missing decoder degrades to name-only without error.

### Phase 3 — Optimize
- Preview export from Lua, `histogram.py` + rule tags, optimize prompt + strict JSON output, transcript rendering.
- **Accept:** on a deliberately underexposed high-ISO test raw, Optimize recommends exposure-raise + denoise (profiled) + tone adjustments with plausible values; output is valid JSON on 3 different models.

### Phase 4 — Vision
- `/vision` endpoint, two-pass describe→recommend, privacy gate (localhost-or-consent), vision-capable preset flag.
- **Accept:** portrait test image yields subject-aware suggestions (e.g., skin tone via color calibration, background separation via tone eq masks); with a cloud preset and consent off, request is refused with a clear message.

### Phase 5 — Apply via styles
- Encoders for Tier 1 codecs, `styles.py` + round-trip validation, `/style`, Lua import/apply + "Apply style" button, style naming/cleanup.
- **Accept:** Optimize → Apply style produces a visible, sane edit on a test raw; the style appears in darktable's styles list under `ai-assistant/`; partial-encodability path shows manual steps for the rest.

### Phase 6 — Polish & packaging
- Tier 2 codecs + full Tier 2 corpus; long-tail corpus stubs; install scripts (venv creation, luarc registration); error surfaces (helper down, no API key, no network); README with per-OS install; settings UI complete; CI (pytest + a Lua lint, fixture matrix for dt 4.6/5.0/5.2).
- **Accept:** clean-machine install on each OS in < 10 min following README; all tests green.

---

## 10. Testing strategy

- **Unit:** codecs (decode fixtures → known values, encode → byte-identical where possible), xmp parser (multi-instance, history_end, compressed+plain params), histogram rules (synthetic images: pure black, clipped sky, blue cast), RAG (query→expected file hits), style round-trip.
- **API:** FastAPI TestClient with a **mock OpenAI server** (canned + JSON-mode responses) so tests run offline.
- **Manual matrix:** dt 4.6/5.x × Linux/Windows/macOS × (Ollama local, one cloud endpoint); checklist in `tests/MANUAL.md`.
- **Fixtures to gather early:** XMPs saved from each targeted dt version with every Tier 1 module enabled at known slider values (create these by hand in darktable; record the values in a YAML next to each XMP).

## 11. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| darktable changes params struct (modversion bump) in a release | decoders return null | version-keyed codecs; null-decode degrades to name-only; CI fixture matrix per dt release |
| XMP stale or disabled by user pref | wrong edit state | mtime check, GUI-action flush, library.db fallback, explicit "state as of <time>" note in context |
| Lua API differences across dt versions | UI breakage | api_version guards + pcall around optional calls; target 4.6+ |
| Endpoint lacks JSON mode / vision | broken optimize/vision | capability flags per preset; fenced-JSON fallback parser |
| Helper orphaned or port conflict | zombie process | port-0 bind, heartbeat self-exit, PID+token file, startup kills stale instance |
| Shell-quoting/paths on Windows | curl calls fail | JSON bodies via temp files, quoted paths, `install.ps1` tested in CI runner |
| User privacy (cloud image upload) | trust loss | image leaves machine only on vision requests, only with per-preset consent, downscaled ≤ configured edge |

## 12. Out of scope (v1)

Direct history-stack manipulation; streaming token display; embeddings/vector search; masks/parametric blending in generated styles (blend params default only); non-OpenAI-compatible provider protocols; localization; darktable < 4.6.

## 13. References for the implementing agent

- Lua API manual: https://docs.darktable.org/lua/stable/ (esp. `types/dt_lua_image_t`, `darktable.styles`, `darktable.new_widget`, `darktable.register_lib`, `darktable.preferences`, `darktable.control`)
- Building UI elements: https://docs.darktable.org/usermanual/development/en/lua/building-ui-elements/
- Example lib module: https://github.com/darktable-org/lua-scripts/blob/master/examples/moduleExample.lua (also study `tools/script_manager.lua` and any script using `dt.control.execute` + curl, e.g. `contrib/gimp.lua` patterns)
- Module reference (RAG source material): https://docs.darktable.org/usermanual/development/en/module-reference/
- Params structs ground truth: `src/iop/*.c` in https://github.com/darktable-org/darktable at the targeted release tag
- Lua cannot access history stack (community confirmation): https://discuss.pixls.us/t/accessing-history-stack-or-sidecar-from-lua-script/52322
