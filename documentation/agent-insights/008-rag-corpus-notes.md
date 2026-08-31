# 004 — RAG module library: corpus, sourcing and retrieval notes

Written by W3 (branch `feat/rag`). Read this before editing anything under
`helper/data/module_library/`, `helper/dt_ai_helper/rag.py`,
`scripts/build_library.py` or `tests/test_rag.py`.

## What exists

| Artefact | Purpose |
| --- | --- |
| `helper/data/module_library/*.md` | 89 module entries, one per darktable op |
| `helper/data/module_library/_SOURCES.md` | attribution; excluded from the corpus |
| `helper/dt_ai_helper/rag.py` | corpus loader + `Retriever` interface + BM25 backend |
| `scripts/build_library.py` | corpus validator, exits non-zero on violations |
| `tests/test_rag.py` | 65 offline tests |

Coverage: **89 entries — 50 full, 39 stub.** 23,749 words total. Full entries
run 261–586 words (median 416), matching plan §8's ~300–600 target; the two
below 300 (`flip`, `velvia`) are modules that genuinely have three or fewer
controls. Stubs run 47–104 words. Tier 1 (12/12) and Tier 2 (10/10) from plan
§7.3 are all present and all full, except `clipping` (deprecated crop-and-rotate)
which is deliberately a stub — the plan lists it only as the legacy alias of
`crop`, and the validator whitelists it.

## Ground truth: where the facts came from

Two sources, both checked at authoring time (2026-08), both GPL-compatible:

1. **darktable user manual, module reference**, development branch —
   `https://docs.darktable.org/usermanual/development/en/module-reference/processing-modules/`.
   Every tab name, slider name, option list and documented default in a full
   entry was read off the corresponding manual page. Nothing was written from
   memory. Where the manual does not state a numeric range (it often doesn't),
   the entry says "typical …" and gives a practitioner range rather than
   inventing a documented one.
2. **`darktable-org/darktable` `src/iop/`** file listing at tags
   `release-5.0.1` and `master`, fetched through the GitHub contents API. This
   is the authority for **internal op names**, which is what the filenames are.
   The manual never prints op names, so guessing them from display names is the
   main hallucination risk in this task.

### Op-name traps found while doing this

* `surface blur` is **`bilateral`**, and its source file is `bilateral.cc`, not
  `.c` — a `.c`-only listing misses it entirely. `lens`, `tonemap` and
  `lut3dgmic` are also C++.
* `astrophoto denoise` is the renamed **`nlmeans`**.
* `contrast & texture` is **`contrastntexture`** (no ampersand, no underscore).
* `framing` is **`borders`**; `composite` is **`overlay`**;
  `external raster mask` is **`rasterfile`**; `unbreak input profile` is
  **`profile_gamma`**; `color look up table` is **`colorchecker`**;
  `raw black/white point` is **`rawprepare`**; `rgb primaries` is
  **`primaries`**; `color equalizer` is **`colorequal`** (a *different* module
  from `colorzones`).
* `agx`, `colorharmonizer`, `contrastntexture` and `rasterfile` exist only on
  `master`, not in `release-5.0.1`. They are documented; a helper targeting
  4.6 will simply never see them in a history stack.
* Ops excluded on purpose because they never appear in a user history stack:
  `gamma`, `finalscale`, `overexposed`, `rawoverexposed`, `mask_manager`,
  `useless`, `ashift_lsd`, `ashift_nmsimplex`, `lut3dgmic`.

The full accepted list lives in `KNOWN_OPS` in `scripts/build_library.py`. When
darktable 5.x adds modules, update that constant *and* add the entry — the
validator fails on an op it does not know, which is the intended tripwire.

## Template deviation from plan §8

Plan §8's template is followed exactly, with **one addition**: a `synonyms:`
header line after `group:`. §8 says "frontmatter-style first lines make op-name
and synonyms exact-match findable" but the sample template has no synonyms line,
so it was added. It carries the photographer vocabulary for that module and is a
large part of why BM25 works as well as it does — the synonym *map* in `rag.py`
only covers general vocabulary, while the per-file `synonyms:` line covers the
module-specific words.

Section order is fixed: `group`, `synonyms`, `purpose`, `use_when`,
`do_not_combine`, `key_controls`, `visual_effect`, `pitfalls`, `pairs_with`.
Stubs carry the first four only. The parser classifies an entry as **full** iff
it has a `key_controls` section — that is the single discriminator, used by both
the validator's report and `ModuleDoc.is_full`.

## Synonym strategy

`SYNONYMS` in `rag.py` maps *what a photographer types* to *terms that appear in
the corpus*. Design rules, kept deliberately simple:

* **Expansion, never substitution.** The original query tokens always survive;
  expansions are appended. A wrong synonym therefore degrades ranking slightly
  instead of breaking a query.
* **Phrase keys are substring-matched** against the lowercased query, and are
  tried longest-first, so `"white balance"` fires before `"wb"`. Single-word
  keys are matched against tokens.
* Keys are grouped by the *complaint* a user makes ("too warm", "blown out",
  "make it punchier", "leaning buildings"), not by module. The plan's four
  seed mappings (`wb`, `clarity`, `curves`, `hdr look`) are all present, plus
  about 120 more covering exposure, highlights/shadows, tone mapping, contrast,
  sharpness, noise, colour, geometry, retouching and output.
* Expansion values must be single lowercase tokens; `test_synonym_map_has_no_
  empty_expansions` enforces this.

### Two ranking adjustments beyond plain BM25

Both exist because plain BM25 gave demonstrably wrong answers:

1. **`op_boost` (+5.0 flat)** when a query token equals a module's op name or a
   word of its display name. Without it, "what does filmicrgb do" does not
   reliably return `filmicrgb.md` first, because op names are rare tokens that
   also appear in other files' `pairs_with` lines.
2. **`deprecated_penalty` (×0.45)** for entries whose `group:` line contains
   `deprecated`. Without it, "i scanned a film negative" returned `invert`
   (deprecated) above `negadoctor` (its replacement), and "dust spots" returned
   `spots` above `retouch`. Deprecated modules must stay retrievable — the
   assistant has to explain an old history stack — but must not be recommended
   over their replacements. This is why the deprecated long tail is documented
   at all rather than omitted.

Both are constructor arguments, so they are tunable without editing the class.

## Retriever interface

`Retriever` is an ABC with a single abstract method
`retrieve(query, k=4) -> list[RetrievalResult]`, plus a concrete
`retrieve_text()` that formats for verbatim prompt injection. `BM25Retriever` is
the v1 implementation. An embedding backend replaces it by subclassing
`Retriever`; `tests/test_rag.py::test_an_alternative_backend_satisfies_the_
interface` exercises exactly that path with a fake backend, so the seam is
tested, not just asserted in prose.

`get_retriever()` is an `lru_cache`d factory — building the BM25 index reads 89
files and tokenises ~24k words. Do not construct `BM25Retriever()` per request.

Chunking is whole-file, per plan §8. `format_context()` joins entries with
`\n\n---\n\n` and does not truncate: at top-k=4 the worst case is roughly four
600-word entries, about 3.5k tokens, which is acceptable for the chat prompt.

## Open questions for the orchestrator

1. **Packaging.** `helper/pyproject.toml` has
   `[tool.setuptools.packages.find] include = ["dt_ai_helper*"]`, and the corpus
   lives at `helper/data/module_library`, *outside* the package. Editable
   installs work (that is what `default_corpus_dir()` resolves to, and what CI
   runs), but a non-editable wheel would ship **without the corpus**. Fixing it
   means either moving the corpus to `dt_ai_helper/data/` or adding
   package-data/`MANIFEST.in` config. `pyproject.toml` is not W3-owned, so this
   is left as a decision. `rag.py` already honours the
   `DT_AI_HELPER_MODULE_LIBRARY` environment variable as an escape hatch.
2. **Corpus refresh.** The entries pin darktable 5.x behaviour. When the target
   dt version moves, the manual pages must be re-read; `scripts/build_library.py`
   validates *structure*, and cannot detect a slider that has been renamed
   upstream. There is no automated freshness check and I do not think one is
   worth building — but a version stamp in `_SOURCES.md` should be bumped
   whenever entries are revised.
3. **No `pairs_with` graph validation.** `pairs_with` and `do_not_combine` name
   modules in prose (display names, not op names) and are not machine-checked
   against the op list. If a later phase wants to reason over the module graph,
   those lines should be reformatted as op-name lists first.
