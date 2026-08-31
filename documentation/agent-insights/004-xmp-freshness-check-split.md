# 004 — XMP freshness check: split between Lua and helper

**Status:** documented design deviation from a literal reading of plan
§5.1 item 3, worth a second look by whoever implements `xmp.py` (W4) /
`/optimize` + `/chat` wiring (W5/W6).

## What the plan says

> XMP freshness check: compare sidecar mtime against `image.change_timestamp`;
> if stale, attempt `darktable.gui.action("lib/copy_history/write sidecar
> files", ...)` guarded by `pcall`, then tell the helper which source to
> trust (`xmp` vs `db`).

Read literally, this puts the mtime-vs-`change_timestamp` comparison — and
therefore the `xmp`-vs-`db` decision — on the Lua side.

## Why the Lua side does not do the mtime comparison itself

darktable's bundled Lua has no `os.stat`/`lfs`-equivalent in its guaranteed
standard library surface (confirmed by `lua-scripts` reference code, which
shells out or uses `io.popen`/batch files for this kind of thing rather than
a filesystem-stat call). Getting a sidecar's mtime from Lua therefore means
either:

- `io.popen("stat ...")` — plain Lua I/O, not routed through
  `dt.control.execute`, so (unlike `control.execute`/`control.sleep`) there
  is no documented guarantee it doesn't block darktable's main loop; or
- the same "write a shell script, `dt.control.execute` it, read the output
  file back" pattern already used for curl and for launching the helper —
  works, but needs a different one-liner per OS (`stat -c %Y` on Linux,
  `stat -f %m` on macOS, a PowerShell `Get-Item` incantation on Windows),
  each with its own quoting/parsing edge cases, for a check whose result is
  only ever used to decide between two strings (`"xmp"` / `"db"`) that the
  Python side (which has trivial, portable `os.path.getmtime`) could decide
  just as well itself.

## What this implementation actually does

`lua/dt-ai-assistant.lua`'s `build_image_context()`:

1. Always calls `attempt_sidecar_flush()` first (the `pcall`-guarded
   `darktable.gui.action("lib/copy_history/write sidecar files", 0, "",
   "activate", 1)` from the plan) when "include edit state" is checked, to
   maximize the chance the on-disk sidecar is current *before* anything
   reads it.
2. Sends the sidecar path and the image's own `change_timestamp` string
   (from `dt_lua_image_t.change_timestamp`) to the helper as-is, inside
   `image_context`.
3. Does **not** independently compute or send an `xmp`/`db` `history_source`
   hint. That decision is left entirely to `xmp.py`/`dbfallback.py`, which
   already need to open the sidecar file regardless (to parse it) and can
   get its mtime for free from `os.path.getmtime()`.

The Lua side does *not* currently render an explicit "sidecar may be stale"
warning in the transcript before sending — that half of plan item 3 is not
implemented. If a future worker wants that UX, the cleanest way to add it
without giving Lua a stat() problem is to have the helper's response
(`/chat`, `/optimize`, `/vision` job result) include which `history_source`
it actually used and a `staleness` note, and have Lua just print whatever
the helper says. That would keep the single source of truth for "is this
XMP current" in one place (Python) instead of two.

## If you disagree with this split

This is exactly the kind of interface question the plan's own conventions
doc asks to be raised rather than changed unilaterally (see
`documentation/agent-insights/002-conventions-for-subagents.md` → "API
contract discipline"). If a future worker wants Lua to make the trust
decision itself, note it in that worker's PR description and update this
file with the correction — don't silently diverge.
