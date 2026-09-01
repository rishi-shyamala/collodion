# collodion — darktable AI Edit Assistant

An AI assistant panel for [darktable](https://www.darktable.org/): chat about your edit, get histogram/EXIF-driven recommendations, run vision analysis on the image, and optionally apply suggestions as darktable styles. Works with any OpenAI-compatible LLM endpoint (OpenAI, OpenRouter, Groq, Ollama, LM Studio, vLLM) — fully local operation is supported.

**Status:** under active development, all planned phases (0-6) implemented; no manual verification against a real darktable install has happened yet (see `tests/MANUAL.md`). See [darktableaiassistantplan.md](darktableaiassistantplan.md) for the full architecture and implementation plan.

## Architecture

- `lua/dt-ai-assistant.lua` — sidebar lib module inside darktable (chat UI, context collection, style application). No network or heavy work in Lua; all LLM/network calls happen in the helper.
- `helper/` — local Python helper service (FastAPI on `127.0.0.1`, bearer-token authed) that does XMP parsing, histogram analysis, RAG retrieval over a bundled module library, LLM calls, and `.dtstyle` generation.
- `helper/dt_ai_helper/data/module_library/` — plain-text RAG corpus: one file per darktable processing module, bundled inside the Python package so it ships in the installed wheel.
- The full as-implemented HTTP contract between the two sides is documented in `documentation/agent-insights/011-api-contract.md`.

## Requirements

- darktable 4.6+ (Lua API 9.x); developed against 4.6/5.0/5.2 semantics, see `tests/MANUAL.md` for what's actually been exercised.
- Python 3.10+
- `curl` on PATH (used by the Lua side to talk to the local helper over HTTP)
- An OpenAI-compatible LLM endpoint: a local one (e.g. [Ollama](https://ollama.com/), LM Studio, vLLM) for fully offline use, and/or a cloud API key (OpenAI, OpenRouter, Groq, ...)

## Install

Each install script: creates a Python virtual environment under darktable's config directory, installs the `dt-ai-helper` package into it (editable, from this repo), copies `lua/dt-ai-assistant.lua` into darktable's `lua/` directory, and appends `require "dt-ai-assistant"` to darktable's `luarc` if it isn't already there. All steps are idempotent — re-running either script is safe.

### Linux / macOS

```sh
./scripts/install.sh
```

Default darktable config directory: `~/.config/darktable` (Linux, honoring `$XDG_CONFIG_HOME`) or `~/Library/Application Support/darktable` (macOS). Override with `--darktable-config-dir`, `--venv-dir`, or `--python` — run `./scripts/install.sh --help` for details.

### Windows

```powershell
.\scripts\install.ps1
```

Default darktable config directory: `%LOCALAPPDATA%\darktable`. Override with `-DarktableConfigDir`, `-VenvDir`, or `-Python`. **This script has not been run against a real Windows darktable install by any contributor so far** — review it before trusting it blindly, and see `tests/MANUAL.md`'s Windows items.

### After running the install script

1. Start (or restart) darktable and open the "lua options" tab in preferences. You should see an "AI assistant" section with several `AI assistant: ...` preferences.
2. Set **"AI assistant: python interpreter"** to the venv's Python the install script printed (e.g. `~/.config/darktable/ai-assistant-venv/bin/python`) — this is how the Lua side knows which interpreter has `dt-ai-helper` installed. Alternatively, leave it blank and instead set **"AI assistant: helper launch command override"** to `<venv-python> -m dt_ai_helper.main` for full control over the launch command.
3. Fill in at least one model preset (see Configuration below).
4. Restart darktable (or reopen the darkroom/lighttable view) so the AI assistant panel launches the helper and shows "helper running" in its status line.

### Manual install (no script)

If you'd rather not run the install script: `pip install -e helper/` into any Python 3.10+ environment, copy `lua/dt-ai-assistant.lua` into darktable's `lua/` directory, add `require "dt-ai-assistant"` to darktable's `luarc`, and point the "python interpreter" preference at that environment's Python.

## Configuration

All configuration lives in darktable's own Lua preferences (preferences → lua options → "AI assistant: ..."); nothing is stored outside darktable's preference database except the helper's own runtime file (port + auth token, see `documentation/agent-insights/003-runtime-file-location.md`) and log.

### Model presets

Up to 5 preset slots, each with:

| Field | Meaning |
|---|---|
| `name` | Display name shown in the model picker combobox |
| `base_url` | OpenAI-compatible base URL, e.g. `https://api.openai.com/v1`, `http://127.0.0.1:11434/v1` (Ollama), `https://openrouter.ai/api/v1` |
| `api_key` | API key, if the endpoint requires one. Stored in darktable's Lua preferences, **not encrypted at rest** |
| `model` | Model identifier sent as the `model` field, e.g. `gpt-5.2`, `qwen3-vl:8b`, `meta-llama/llama-4-scout` |
| `supports_vision` | Enable only if this model/endpoint accepts image inputs — required for "Analyze image" |

Leave a slot's `name` empty to disable it. The active preset is chosen via the model picker combobox in the panel; switching presets takes effect on the next request, no restart needed.

**Ollama example** — run `ollama pull qwen3-vl:8b` (or any vision-capable model), then configure a preset with `base_url = http://127.0.0.1:11434/v1`, `model = qwen3-vl:8b`, `api_key` empty, `supports_vision = true`. No cloud upload gate applies to this preset since it's local (see Privacy below).

### Other preferences

- **preview max edge (px)** — longest edge of the JPEG preview exported for Optimize/Analyze image requests (default 1024).
- **request timeout (s)** — per-`curl`-call timeout and overall job-polling budget (default 60).
- **allow image upload to cloud endpoints** — privacy toggle, off by default. See Privacy below.

### Privacy: cloud image upload

"Analyze image" sends the exported preview to whichever model preset is active. If that preset's `base_url` is not `127.0.0.1`/`localhost`, the image is refused **unless** "allow image upload to cloud endpoints" is on — checked both in Lua (so the preview is never even exported/sent) and again in the helper (so a misconfigured or bypassed Lua check can't leak an image either). Local endpoints (Ollama, LM Studio, etc.) are always allowed regardless of this toggle. Chat and Optimize never send image bytes at all, only text (EXIF, decoded module state, histogram stats).

## Usage

The AI assistant panel appears in both the darkroom and lighttable right panel (collapsible like any other module). With an image selected/hovered:

- **Send** — sends the text box's contents as a chat message, optionally with your current edit state (see the "include my current edit state in context" checkbox) attached as context. Answers reference real module/slider names grounded in the bundled module library.
- **Optimize** — exports a preview, computes histogram/EXIF-driven issue tags, and asks the model for a structured recommendation (assessment + prioritized module settings). If any recommended module is encodable, a `.dtstyle` is built automatically and "Apply style" becomes enabled.
- **Analyze image** (vision) — exports a preview and sends it to a vision-capable preset for a two-pass description → module-recommendation. Requires the active preset to have `supports_vision` on; subject to the cloud-upload privacy gate above.
- **Apply style** — enabled once a response carries a style; imports and applies the generated `.dtstyle` to the current image via `darktable.styles.import`/`darktable.styles.apply`. Styles are named `ai-assistant/<slug>-<timestamp>` and show up in darktable's own styles list, where they can be renamed, reused, or deleted like any other style.
- **Clear** — resets the visible transcript and starts a fresh conversation history for the current image (server-side history is keyed per image, not shared across images).

The model picker combobox selects which configured preset is active; the "include my current edit state in context" checkbox controls whether EXIF + the enabled-module list (parsed from the XMP sidecar, falling back to `library.db`) is attached to Send/Optimize requests.

## Troubleshooting

- **"(helper unavailable: ...)"** — the Python helper isn't reachable. Check `helper.log` next to the runtime file — `~/.cache/dt-ai-helper/helper.log` on Linux, `~/Library/Caches/dt-ai-helper/helper.log` on macOS, `%LOCALAPPDATA%\dt-ai-helper\helper.log` on Windows (see `documentation/agent-insights/003-runtime-file-location.md` for the exact rules) — for a Python traceback; the most common cause is the "python interpreter" preference not pointing at an environment with `dt-ai-helper` installed. Try running `<that python> -m dt_ai_helper.main` by hand in a terminal to see the error directly.
- **"No model preset is configured yet"** — fill in at least one preset slot's `name`/`base_url`/`model` in preferences.
- **API key / 401 errors from the LLM endpoint** — double-check the preset's `api_key` field; some providers (OpenRouter, Groq) use a different header/prefix convention than OpenAI's, but all speak the same `Authorization: Bearer <key>` shape this client sends.
- **Analyze image refuses with "is a cloud endpoint and ... is off"** — turn on "allow image upload to cloud endpoints" in preferences, or switch to a local/vision-capable preset.
- **Chat/Optimize answers don't reflect recent edits ("stale XMP")** — darktable only writes sidecars when its own "write sidecar file for each image" core preference is enabled (default: after edits). If you've changed that default, edits may not be reflected until a sidecar is written; the helper falls back to `library.db` when possible but that path currently needs `db_path`/`image_id` fields the Lua side doesn't send yet (see `documentation/agent-insights/011-api-contract.md`).
- **Helper process seems stuck / using resources with darktable closed** — the helper self-exits ~10 minutes after darktable stops sending it heartbeats; it should never outlive darktable by more than that.
- **Windows: nothing happens when the panel says "starting helper..."** — this launch path is the least-tested part of the project (see `tests/MANUAL.md`); check `helper.log` under `%LOCALAPPDATA%\dt-ai-helper\` and consider running the launch command manually.

## Development

```sh
cd helper
python -m venv .venv && . .venv/bin/activate  # .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
pytest ../tests -q
ruff check . ../tests
```

Validate the RAG module library structure with `python scripts/build_library.py`. Lint the Lua file with `luac -p lua/dt-ai-assistant.lua` and, if installed, `luacheck lua --globals darktable dt --no-max-line-length`.

CI configuration lives at `ci/github-ci.yml` rather than `.github/workflows/ci.yml` for now — see the note at the top of that file for why and how to enable it.

Contributor/agent conventions: see [CLAUDE.md](CLAUDE.md) and `documentation/agent-insights/` (start with `001-orchestration-log.md` for project history and `011-api-contract.md` for the Lua↔helper contract).

## Attribution

The RAG module library (`helper/dt_ai_helper/data/module_library/`) is derived from the [darktable user manual](https://docs.darktable.org/usermanual/)'s module reference (GPL-licensed), rewritten into a retrieval-oriented template rather than reproduced verbatim. See `helper/dt_ai_helper/data/module_library/_SOURCES.md` for details.

## License

GPL-3.0-or-later.
