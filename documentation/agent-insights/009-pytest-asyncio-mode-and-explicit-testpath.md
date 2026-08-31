# 009 — `pytest ../tests -q` can silently drop `asyncio_mode = auto`

Written by W5 (branch `feat/llm-chat`) while wiring up `tests/test_llm.py`,
whose `OpenAIChatClient` tests are plain `async def test_...` functions
(no prior test file in the suite had any).

## The symptom

`helper/pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
testpaths = ["../tests"]
asyncio_mode = "auto"
```

Running exactly the command this repo's conventions and CI prescribe —
`cd helper && pytest ../tests -q` — collected all the async test functions
but failed every one of them with:

```
async def functions are not natively supported.
You need to install a suitable plugin for your async framework...
```

...even though `pytest-asyncio` was installed and its `asyncio` marker was
registered (`pytest --markers` showed it). Passing `-o asyncio_mode=auto`
explicitly on the command line fixed it immediately, which proved the
plugin was fine and the *ini file itself* wasn't being read for this
invocation.

## Root cause

On the pytest version this environment resolved (9.1.1), passing an
explicit path argument that lives *outside* the invocation cwd's own
directory (`../tests` from inside `helper/`) changes how pytest computes
the common-ancestor starting point for rootdir/inifile discovery. Just
running bare `pytest -q` from `helper/` (relying on `testpaths` in the ini
instead of repeating the path on the command line) finds `helper/pyproject.toml`
and applies `asyncio_mode = auto` correctly — same tests, same cwd, only
the presence of the explicit `../tests` argument differs.

This is intermittent-looking and easy to misdiagnose as "pytest-asyncio
isn't installed" (the error message actively suggests that) when the real
issue is config-file discovery, not the plugin.

## What this branch does about it

Rather than relitigate the prescribed CI invocation (`pytest ../tests -q`
is what `ci/github-ci.yml` and the subagent conventions doc both specify),
every `async def test_...` in `tests/test_llm.py` carries an explicit
`@pytest.mark.asyncio` decorator. The marker always works regardless of
whether `asyncio_mode = auto` from the ini got picked up — it's the
belt-and-suspenders fix that doesn't depend on rootdir discovery behaving
any particular way across pytest versions/environments.

## If you add more async tests anywhere in `tests/`

Don't rely solely on `asyncio_mode = auto` in `helper/pyproject.toml` —
decorate each `async def test_...` with `@pytest.mark.asyncio` too. It costs
nothing when the ini setting *does* get picked up, and saves the next
person from re-debugging this.
