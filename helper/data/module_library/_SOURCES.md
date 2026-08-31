# Sources and attribution

This corpus is a rewritten, retrieval-oriented condensation of the **darktable
user manual**, module reference section:

  https://docs.darktable.org/usermanual/development/en/module-reference/

The darktable user manual is published by the darktable project under the
GNU General Public License, version 3 or later — the same licence as this
repository (see `LICENSE`). Module display names, internal operation names,
tab names, control/slider names, option lists and documented defaults were
taken from that manual (development branch, corresponding to darktable 5.x)
and from the module source file names in `darktable-org/darktable`
`src/iop/` at tags `release-5.0.1` and `master`, which is the authority for
the internal op names used as filenames here.

The prose (purpose, use_when, visual_effect, pitfalls, pairs_with) is written
for this project: it is grounded in the manual's factual content but phrased
for BM25 retrieval and for grounding an LLM assistant, not as documentation.

Files whose names begin with `_` (such as this one) are metadata and are
excluded from the retrieval corpus and from the validator.
