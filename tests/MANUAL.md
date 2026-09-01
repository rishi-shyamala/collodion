# Manual test matrix

Everything in `tests/` runs offline and is part of CI. The items below need
a real darktable install (and, for some, a real LLM endpoint) and cannot be
automated in this environment — no darktable install has been available to
any agent iteration so far (see `documentation/agent-insights/005`, `006`,
`007`). Run this checklist by hand before calling a release "done", and
update it (with dates/results/darktable version) as items get verified.

## Coverage matrix

Run at least once per darktable major line × OS × backend combination:

| darktable | OS | Backend | Status |
|---|---|---|---|
| 4.6.x | Linux | Ollama (local) | not yet run |
| 4.6.x | Linux | cloud endpoint | not yet run |
| 4.6.x | Windows | Ollama (local) | not yet run |
| 4.6.x | Windows | cloud endpoint | not yet run |
| 4.6.x | macOS | Ollama (local) | not yet run |
| 4.6.x | macOS | cloud endpoint | not yet run |
| 5.0.x/5.2.x | Linux | Ollama (local) | not yet run |
| 5.0.x/5.2.x | Linux | cloud endpoint | not yet run |
| 5.0.x/5.2.x | Windows | Ollama (local) | not yet run |
| 5.0.x/5.2.x | Windows | cloud endpoint | not yet run |
| 5.0.x/5.2.x | macOS | Ollama (local) | not yet run |
| 5.0.x/5.2.x | macOS | cloud endpoint | not yet run |

"Ollama (local)" = an OpenAI-compatible preset pointed at
`http://127.0.0.1:11434/v1` (or LM Studio/vLLM equivalent) with a
vision-capable model (e.g. a `qwen*-vl` variant) for the vision items.
"cloud endpoint" = any one hosted OpenAI-compatible provider (OpenAI,
OpenRouter, Groq, ...) with both a text and a vision-capable model
configured as separate presets.

For each cell, run through **every** item below at least once; you don't
need to re-derive the checklist per cell, just tick off which cells you've
covered.

## Install

- [ ] `scripts/install.sh` (Linux) completes without error on a machine
      with no prior collodion install; darktable's lua options tab shows
      the "AI assistant" preferences afterwards.
- [ ] `scripts/install.sh` (macOS) — same, including that the default
      `--darktable-config-dir` (`~/Library/Application Support/darktable`)
      is correct for the installed darktable version.
- [ ] `scripts/install.ps1` (Windows) completes without error in PowerShell
      (both Windows PowerShell 5.1 and PowerShell 7+, if available).
      **Never run on a real Windows box by any agent iteration so far —
      review the script carefully before trusting it, and report back
      any fixes needed as a new agent-insights file.**
- [ ] Re-running the install script a second time is a no-op for the
      `luarc` require line (doesn't duplicate it) and successfully
      re-installs/upgrades the helper package.
- [ ] After install + setting `python_path`/`helper_command_override` to
      the created venv (per the script's printed instructions) and
      restarting darktable, the "AI assistant" panel appears in both the
      darkroom and lighttable right panel, and its status line reads
      "helper running" within a few seconds.

## Helper lifecycle

- [ ] Quitting darktable also terminates the helper process (check with
      `ps`/Task Manager) rather than leaving it orphaned.
- [ ] Killing darktable uncleanly (e.g. `kill -9`), then restarting it,
      does not leave two helper processes running — `kill_stale_instance()`
      should reap the orphan (check the pid in
      `<cache-dir>/dt-ai-helper/runtime.json` before/after).
- [ ] Leaving darktable open and idle for >10 minutes without touching the
      AI assistant panel: the helper self-exits (watchdog timeout); the
      next Send/Optimize/Analyze click transparently relaunches it (this
      exercises `ensure_helper_running()`'s launch-on-demand path, not just
      the darktable-startup launch path).
- [ ] **Windows detached launch**: confirm the helper actually stays alive
      in the background after `launch_helper()`'s `.bat` file returns
      (i.e. the `start "" /B ...` backgrounding actually works as intended
      on a real Windows install) — flagged as unverified since PR #2
      (`documentation/agent-insights/003-runtime-file-location.md`).
- [ ] `--runtime-file` is actually being passed on the launch command line
      (check `<cache-dir>/dt-ai-helper/helper.log`'s process listing, or
      add a temporary print) — added in this PR (W8) to remove the
      "both sides must independently compute the same default" hazard;
      confirm it didn't regress the happy path where the default and the
      explicit flag agree.

## Chat (Phase 1)

- [ ] With a local Ollama preset: "how do I make the sky more dramatic?"
      returns steps naming real modules/sliders (cross-check a couple
      against `helper/dt_ai_helper/data/module_library/*.md`), not
      hallucinated names.
- [ ] Same question against a cloud preset returns comparably grounded
      answers.
- [ ] Swapping the model preset combobox mid-session and sending another
      message uses the new preset without restarting darktable or the
      helper (Phase 1 acceptance criterion).
- [ ] "Clear" empties the transcript and starts a fresh server-side
      history (ask something that depends on prior context after Clear;
      it should not remember).
- [ ] Toggling "include my current edit state in context" off and on
      changes whether the assistant can answer "what have I already done
      to this photo?" correctly.

## Edit-state awareness (Phase 2)

- [ ] **Real-XMP validation** (outstanding since PR #3/#4,
      `documentation/agent-insights/005-xmp-params-encoding.md`): apply a
      few Tier-1 module edits (exposure, filmic rgb, color balance rgb,
      tone equalizer, highlights, white balance, sharpen, denoise
      (profiled), crop) at known slider values in real darktable, save the
      sidecar, and confirm `helper/dt_ai_helper/xmp.py` decodes them to
      the same values shown in darktable's UI. Record the XMP + a YAML of
      expected values in `tests/fixtures/` once done, matching the existing
      `handwritten_multi_instance.xmp`/`.yaml` pair's format, and turn this
      into an automated fixture test.
- [ ] Ask "what have I already done to this photo?" with edit state
      included; confirm the assistant lists the enabled modules with
      correctly decoded values, and that a module with a decoder gap
      (e.g. `diffuse`) degrades to "(enabled, values unavailable)" rather
      than erroring or fabricating values.
- [ ] Disable "write sidecar file for each image" in darktable's core
      preferences, make an edit, and confirm the assistant still gets a
      usable (if possibly stale) answer rather than crashing.

## Optimize (Phase 3)

- [ ] On a deliberately underexposed, high-ISO test raw: Optimize
      recommends exposure-raise + denoise (profiled) + tone adjustments
      with plausible values, across at least 2 different models/presets,
      and the JSON recommendation parses successfully every time (no
      `chat_json` fallback-to-text failures).
- [ ] "Apply style" (enabled after Optimize returns a style) produces a
      visible, sane edit on the test raw, and the new style appears in
      darktable's styles list under `ai-assistant/`.
- [ ] A recommendation that only touches `denoiseprofile` and/or `crop`
      (no static defaults / no slider mapping — see
      `documentation/agent-insights/007-blendop-defaults.md` §3) shows the
      "no known default parameters" manual step rather than silently
      dropping the module or crashing.

## Vision / Analyze image (Phase 4)

- [ ] **Live vision, local preset**: a vision-capable Ollama model produces
      subject-aware suggestions (e.g. skin tone -> color calibration,
      background separation -> tone eq masks) for a portrait test image.
- [ ] **Live vision, cloud preset, consent off** (`allow_cloud_upload`
      pref unset): Analyze image refuses locally in Lua with the "allow
      image upload to cloud endpoints" message, and no preview is
      exported to a temp file that then gets sent anywhere.
- [ ] **Live vision, cloud preset, consent on**: confirm the request
      actually succeeds end-to-end now that Lua sends `allow_upload` in
      the `/vision` payload (bug fixed in this PR — previously the helper
      always saw `allow_upload: false` regardless of the pref, and cloud
      vision was refused server-side even with consent on locally; see
      `documentation/agent-insights/010-optimize-vision-notes.md` and
      `011-api-contract.md`).
- [ ] Selecting a non-vision-capable preset and clicking Analyze image
      shows the "not marked as vision-capable" message without attempting
      a network call.

## Apply via styles (Phase 5)

- [ ] `darktable.styles.import()`'s **return value** on a live darktable
      install: confirm `do_apply_style()`'s `pcall(dt.styles.import, ...)`
      actually receives a usable style object across the dt versions
      tested (flagged as unverified since PR #2 — the Lua code was written
      against the documented API shape, not exercised against a real
      return value).
- [ ] Applying the same style twice (re-clicking "Apply style" without a
      new Optimize run) doesn't error or duplicate history entries
      unexpectedly.
- [ ] Style files accumulate under darktable's styles directory named
      `ai-assistant/<slug>-<timestamp>` and are deletable/manageable from
      darktable's own styles UI like any other style.

## General error surfaces

- [ ] Helper down / not installed: Send/Optimize/Analyze show a clear
      "(helper unavailable: ...)" message rather than hanging or crashing
      darktable.
- [ ] No API key set on a preset that requires one: the LLM error surfaces
      as a readable job `error` string in the transcript, not a raw
      traceback.
- [ ] No network reachable (cloud preset, network off): times out
      gracefully within the configured `request_timeout` budget and shows
      an error rather than freezing the UI (this is the core "never block
      the darktable UI thread" constraint from plan §2 item 6 — watch that
      the panel and the rest of darktable stay responsive while a request
      is in flight).
