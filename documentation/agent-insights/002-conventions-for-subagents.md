# 002 — Conventions for subagents

You are one worker among several building collodion in parallel. Follow these exactly.

## Ground rules

1. Read `darktableaiassistantplan.md` first. Plan §2 constraints are non-negotiable.
2. You own only the files listed in your task prompt (see ownership map in `001-orchestration-log.md`). Do not edit files owned by another worker; if an interface you need doesn't exist yet, code against the contract in plan §5.2 and stub/mock it in tests.
3. Work happens in your git worktree on your assigned branch. Commit in logical units with clear messages.
4. Before opening the PR: `cd helper && pip install -e ".[dev]" && pytest && ruff check .` must pass (Lua-only work: at minimum `luac -p` or `luacheck` if available).
5. Open the PR with `gh pr create --base main --head <branch>` — title `<area>: <summary>`, body describing what was built, deviations from the plan, and how it was tested. Do NOT merge your own PR; the orchestrator reviews and merges.
6. Document every non-obvious discovery in a new numbered file in `documentation/agent-insights/` and commit it with your branch.

## API contract discipline

The Lua↔helper HTTP contract is plan §5.2. It is the seam between workers — if you believe it must change, do not change it unilaterally; note the proposal in your PR description and in an agent-insights file.

## Offline testing

No test may hit the network. LLM calls are tested against a mock OpenAI-compatible server (FastAPI/httpx MockTransport). Mark anything needing a real darktable install as a manual-test item in your PR body.

## GitHub workflow scope limitation (2026-08-31)

The local `gh` OAuth token lacks the `workflow` scope, so any push containing files under `.github/workflows/` is rejected by GitHub. The CI definition lives at `ci/github-ci.yml` for now — do NOT create files under `.github/workflows/` in your branch. Once the user runs `gh auth refresh -s workflow`, the file moves back (tracked as a W8 task). Run the same checks locally before your PR instead.
