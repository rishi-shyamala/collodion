# 001 — Orchestration log

Started 2026-08-31. Orchestrator: Claude (Fable 5) session; workers: Sonnet (tight/integration tasks) and Opus (creative/free-form tasks) subagents in isolated git worktrees, one feature branch + PR each.

## Work breakdown (maps to plan phases §9)

| # | Branch | Model | Scope | Depends on |
|---|--------|-------|-------|-----------|
| W1 | feat/helper-skeleton | sonnet | FastAPI app: /health, /config, /heartbeat, token+port file, auth middleware, job manager, self-exit; tests | — |
| W2 | feat/lua-frontend | sonnet | lua/dt-ai-assistant.lua: lib module UI, prefs, helper launch/health, curl+polling, apply-style plumbing | contract only |
| W3 | feat/rag | opus | data/module_library corpus (Tier 1+2 full, long tail stubbed), rag.py BM25 + synonyms, build_library.py validator, tests | — |
| W4 | feat/xmp-codecs | sonnet | xmp.py, dbfallback.py, params_codec/ Tier 1 decoders+encoders, fixtures + YAML expectations, tests | — |
| W5 | feat/llm-chat | sonnet | llm.py, prompts.py, /chat wired to jobs + RAG + image_context, mock-OpenAI tests | W1, W3 |
| W6 | feat/optimize-vision | sonnet | histogram.py + rule tags, /optimize strict-JSON, /vision two-pass + privacy gate, tests | W1, W5 |
| W7 | feat/styles | sonnet | styles.py .dtstyle emitter + round-trip validation, /style endpoint, tests | W1, W4 |
| W8 | feat/packaging | sonnet | install.sh/install.ps1, CI polish, README per-OS install, MANUAL.md checklist | all |

Wave 1 (parallel): W1, W2, W3, W4 — disjoint file ownership.
Wave 2 (after W1 merges; W5 also needs W3): W5, then W6 ∥ W7.
Wave 3: W8.

## File ownership map (conflict avoidance)

- W1: helper/dt_ai_helper/{main,api,jobs}.py, tests/test_api.py
- W2: lua/dt-ai-assistant.lua only
- W3: helper/dt_ai_helper/rag.py, helper/data/module_library/*, scripts/build_library.py, tests/test_rag.py
- W4: helper/dt_ai_helper/{xmp,dbfallback}.py, params_codec/*, tests/{fixtures,test_xmp.py,test_codecs.py}
- W5: helper/dt_ai_helper/{llm,prompts}.py, edits to api.py (chat route), tests/test_llm.py
- W6: helper/dt_ai_helper/histogram.py, api.py routes, tests/test_histogram.py
- W7: helper/dt_ai_helper/styles.py, api.py route, tests/test_styles.py
- W8: scripts/*, .github/*, README.md, tests/MANUAL.md

## PR / review log

(appended as PRs land)

### 2026-08-31 — PR #1 (W1, feat/helper-skeleton) MERGED
Verified independently: 10 tests pass, ruff clean. Notes: jobs.py docstring mentions nonexistent `pipelines` module (cleanup for W5); helper's default runtime file is `<platform-cache>/dt-ai-helper/runtime.json` — Lua launcher should pass `--runtime-file` explicitly to avoid path-guessing drift (reconcile with W2's 003-runtime-file-location.md when it lands).

### 2026-08-31 — PR #2 (W2, feat/lua-frontend) MERGED
lua/dt-ai-assistant.lua (~1360 lines): luac-clean, mock-driven callback tests, runtime-file contract cross-checked with W1. Manual-test items outstanding: styles.import() return value on live darktable, Windows detached launch. Follow-up: pass --runtime-file explicitly at launch. Note: insight-file numbers 004 now taken (xmp-freshness-check-split); W3/W4 insight files may need renumbering at merge.

### 2026-08-31 — PR #3 (W4, feat/xmp-codecs) MERGED
XMP parser + Tier 1 codecs (10 ops, current modversions), dbfallback, synthetic fixtures. Verified: 55 tests pass, ruff clean; exposure codec spot-checked against dt 4.6 source (gboolean handled as int32). Orchestrator resolved agent-insights README index merge conflict. Outstanding manual task: validate against real darktable-produced XMPs (insights 005).

### 2026-08-31 — PR #4 (W3, feat/rag) MERGED
89-module corpus (50 full/39 stub, ~24k words), BM25 + synonyms + deprecated-penalty retriever, validator. 119 tests green. Orchestrator renumbered corpus notes to 008 and fixed scripts/ lint. Packaging gap (corpus outside wheel — needs package-data or move into dt_ai_helper/data) assigned to W8.
