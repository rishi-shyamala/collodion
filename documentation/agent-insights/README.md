# agent-insights

Long-term memory for agents (and humans) working on collodion. Every non-obvious discovery, constraint, workaround, decision, or open question gets a numbered markdown file here so future iterations don't rediscover it.

Rules:

- One topic per file, numbered sequentially: `NNN-short-slug.md`. Check existing numbers before adding.
- Write for a reader with zero context: state the problem, what was tried, what the answer is, and links/evidence.
- Never delete a file; if an insight turns out wrong, append a correction with the date.
- The orchestration log (`001-orchestration-log.md`) tracks task decomposition, PR assignments, and review outcomes.

## Index

- `001-orchestration-log.md` — task breakdown, subagent assignments, PR/review log
- `002-conventions-for-subagents.md` — how work is scoped, branch/PR rules, file-ownership map
- `003-runtime-file-location.md` — Lua↔helper runtime file path/contents contract (cross-checked between W1 and W2)
- `004-xmp-freshness-check-split.md` — why the sidecar mtime-vs-change_timestamp freshness decision is delegated to the helper instead of computed in Lua
- `005-xmp-params-encoding.md` — verified `darktable:params` gz/hex encoding, source references, outstanding real-XMP validation task
- `006-codec-notes.md` — per-module struct layout notes for the Tier-1 params codecs
- `008-rag-corpus-notes.md` — RAG corpus sourcing, synonym strategy, op-name traps, coverage stats
- `010-optimize-vision-notes.md` — histogram rule-tag vocabulary, optimize retrieval query mapping, /optimize style-from-job reuse, /vision privacy-gate ordering, and contract deviations
