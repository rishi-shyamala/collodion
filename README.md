# collodion — darktable AI Edit Assistant

An AI assistant panel for [darktable](https://www.darktable.org/): chat about your edit, get histogram/EXIF-driven recommendations, run vision analysis on the image, and optionally apply suggestions as darktable styles. Works with any OpenAI-compatible LLM endpoint (OpenAI, OpenRouter, Groq, Ollama, LM Studio, vLLM) — fully local operation is supported.

**Status:** under active development. See [darktableaiassistantplan.md](darktableaiassistantplan.md) for the full architecture and implementation plan.

## Architecture

- `lua/dt-ai-assistant.lua` — sidebar lib module inside darktable (chat UI, context collection, style application). No network or heavy work in Lua.
- `helper/` — local Python helper service (FastAPI on `127.0.0.1`, token-authed) that does XMP parsing, histogram analysis, RAG retrieval over a bundled module library, LLM calls, and `.dtstyle` generation.
- `helper/data/module_library/` — plain-text RAG corpus: one file per darktable processing module.

## Requirements

- darktable 4.6+ (Lua API 9.x)
- Python 3.10+
- `curl` on PATH (used by the Lua side for localhost HTTP)

## Install

See `scripts/install.sh` (Linux/macOS) or `scripts/install.ps1` (Windows). Detailed per-OS instructions land here as part of Phase 6.

## Development

```sh
cd helper
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Contributor/agent conventions: see [CLAUDE.md](CLAUDE.md) and `documentation/agent-insights/`.

## License

GPL-3.0. The RAG module library is derived from the [darktable user manual](https://docs.darktable.org/usermanual/) (GPL), rewritten for retrieval.
