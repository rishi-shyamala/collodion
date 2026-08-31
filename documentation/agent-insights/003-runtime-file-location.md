# 003 — Helper runtime file location (Lua ↔ Python discovery contract)

**Status:** confirmed, both sides agree. Written by W2 (Lua front-end) after
cross-checking against W1's helper skeleton (`feat/helper-skeleton` branch,
`helper/dt_ai_helper/main.py`) rather than inventing a separate convention.
Recorded here per the task instructions so the two workers' PRs don't drift.

## The contract

The Python helper (`dt-ai-helper`) binds `127.0.0.1` on an OS-assigned port
(bind port 0) and generates a random bearer token at startup. Since the port
isn't known until the process is already running, it writes both to a
well-known "runtime file" that the Lua front-end polls for after launching
the helper.

**Path** (implemented in `main.py:default_runtime_dir()`):

| OS | Path |
|---|---|
| Linux | `$XDG_CACHE_HOME/dt-ai-helper/runtime.json` (falls back to `~/.cache/dt-ai-helper/runtime.json` if `XDG_CACHE_HOME` unset) |
| macOS | `~/Library/Caches/dt-ai-helper/runtime.json` |
| Windows | `%LOCALAPPDATA%\dt-ai-helper\runtime.json` (falls back to `~/AppData/Local/dt-ai-helper/runtime.json`) |

**Contents:** a JSON object, mode 600 (best-effort on platforms without
POSIX permission bits):

```json
{"port": 54213, "token": "<url-safe random string>", "pid": 12345}
```

The file is removed on clean helper shutdown, and a stale entry (from a
previous darktable session that crashed or was killed) is detected via `pid`
and killed by the helper itself on next launch (`kill_stale_instance()` in
`main.py`) before it binds a new port. The Lua side does not need to do any
of that liveness/staleness handling itself — it should simply:

1. Try to read the runtime file and `GET /health` with its token.
2. If that fails (file missing, or health check fails), launch the helper
   and poll for the file to appear (it may take a moment for uvicorn to bind
   and for the file to be written).

## Where each side implements this

- **Python (W1):** `helper/dt_ai_helper/main.py` — `default_runtime_dir()`,
  `default_runtime_file()`, `write_runtime_file()`, `kill_stale_instance()`.
- **Lua (W2):** `lua/dt-ai-assistant.lua` — `default_runtime_dir()`,
  `runtime_file_path()`, `read_runtime_file()`. The Lua implementation
  mirrors the Python one field-for-field and directory-for-directory; if one
  side's default ever changes, the other must change too (there is no
  negotiation protocol — the path itself *is* the contract).

## Launching the helper process (Lua side only, not part of the contract but worth recording)

`dt.control.execute()` on darktable runs a command in a shell and blocks the
calling Lua coroutine until it exits — fine for short curl calls, but the
helper is a long-lived server, so the *launch* command itself must
background/detach so the shell invocation returns almost immediately. The
Lua script writes a tiny platform-native launcher script to
`darktable.configuration.tmp_dir` and executes *that*:

- **Linux/macOS:** a `sh` script doing
  `nohup <cmd> >> <runtime_dir>/helper.log 2>&1 < /dev/null & disown`.
- **Windows:** a `.bat` file doing `start "" /B <cmd> >> <log> 2>&1`, which
  mirrors the approach used by `darktable-org/lua-scripts`'
  `lib/dtutils.system.lua:windows_command()` for working around known
  `dt.control.execute` quoting problems on Windows (that helper writes a
  batch file to `tmp_dir` and executes the file itself rather than passing a
  complex command line inline).

This part was **not** verified against a live Windows darktable install —
flagged as an open uncertainty in the W2 PR description.
