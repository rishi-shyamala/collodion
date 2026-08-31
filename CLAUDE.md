# collodion — repo conventions

Read `darktableaiassistantplan.md` before touching anything. Its §2 "Hard constraints" are load-bearing facts about the darktable Lua API — do not redesign around them.

## Workflow

- Feature branches named `feat/<area>` (e.g. `feat/helper-skeleton`, `feat/rag-corpus`). Never commit to `main` directly; open a PR against `main` and wait for orchestrator review.
- Keep PRs scoped to the files listed in your task. If you must touch a shared file outside your scope, note it prominently in the PR description.
- Record any non-obvious discovery, workaround, or open question in `documentation/agent-insights/` (one markdown file per topic, numbered, e.g. `007-xmp-gz-encoding.md`). This folder is the project's long-term memory across agent iterations — write for a future agent with zero context.

## Code

- Python: 3.10+, type hints, `ruff` clean (config in `helper/pyproject.toml`). Tests with `pytest` under `tests/`. All network-dependent tests must run offline against mocks.
- Lua: single file `lua/dt-ai-assistant.lua`, target darktable Lua API 9.x (dt 4.6+). Guard version-dependent calls with `pcall` + `darktable.configuration` checks. Never block the UI thread longer than a short curl call; use the job/polling pattern from plan §5.3.
- The helper binds `127.0.0.1` only, bearer-token auth on every endpoint, token file mode 600.
- API contract between Lua and helper is plan §5.2 — changing it requires updating both sides and the contract doc in `documentation/agent-insights/`.

## Testing

- `cd helper && pip install -e ".[dev]" && pytest` must pass before opening a PR.
- Fixtures (sample XMPs, preview JPEGs) live in `tests/fixtures/` with a YAML of expected values next to each.
