#!/usr/bin/env python3
"""Validate the RAG module library (plan section 8).

Checks, for every ``helper/data/module_library/<op>.md``:

* the first line is ``# <display name> (<op>)``
* the header's op name matches the filename
* the op name is a known darktable module (see ``KNOWN_OPS``)
* the required sections are present, in the template's order
* full entries additionally carry key_controls / visual_effect / pitfalls /
  pairs_with, at least ``MIN_CONTROLS`` control bullets, a BEFORE and an AFTER
  in visual_effect, and a plausible word count

Then reports full-vs-stub classification and coverage of the plan's Tier 1 and
Tier 2 module lists. Exits non-zero if any check fails.

Usage:
    python scripts/build_library.py [corpus_dir] [--quiet]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "helper"))

from dt_ai_helper.rag import ModuleDoc, parse_module_file

# ---------------------------------------------------------------------------
# Known ops. Source of truth: the .c/.cc files in darktable-org/darktable
# src/iop at tags release-5.0.1 and master. Pure-internal ops that never appear
# in a user history stack (gamma, finalscale, mask_manager, useless, ...) are
# deliberately excluded -- the corpus does not document them.
# ---------------------------------------------------------------------------
KNOWN_OPS = frozenset(
    ["agx", "ashift", "atrous", "basecurve", "basicadj", "bilat", "bilateral", "bloom", "blurs", "borders", "cacorrect", "cacorrectrgb", "censorize", "channelmixer", "channelmixerrgb", "clahe", "clipping", "colisa", "colorbalance", "colorbalancergb", "colorchecker", "colorcontrast", "colorcorrection", "colorequal", "colorharmonizer", "colorin", "colorize", "colormapping", "colorout", "colorreconstruction", "colortransfer", "colorzones", "contrastntexture", "crop", "defringe", "demosaic", "denoiseprofile", "diffuse", "dither", "enlargecanvas", "equalizer", "exposure", "filmic", "filmicrgb", "flip", "globaltonemap", "graduatednd", "grain", "hazeremoval", "highlights", "highpass", "hotpixels", "invert", "lens", "levels", "liquify", "lowlight", "lowpass", "lut3d", "monochrome", "negadoctor", "nlmeans", "overlay", "primaries", "profile_gamma", "rasterfile", "rawdenoise", "rawprepare", "relight", "retouch", "rgbcurve", "rgblevels", "rotatepixels", "scalepixels", "shadhi", "sharpen", "sigmoid", "soften", "splittoning", "spots", "temperature", "tonecurve", "toneequal", "tonemap", "velvia", "vibrance", "vignette", "watermark", "zonesystem"]
)

# Plan section 7.3 curated priority lists.
TIER1_OPS = ["exposure", "filmicrgb", "sigmoid", "colorbalancergb", "toneequal", "highlights", "temperature", "sharpen", "diffuse", "denoiseprofile", "crop", "clipping"]
TIER2_OPS = ["channelmixerrgb", "colorzones", "bilat", "lens", "ashift", "vignette", "graduatednd", "velvia", "lowpass", "retouch"]

REQUIRED_SECTIONS = ("group", "synonyms", "purpose", "use_when")
FULL_SECTIONS = ("key_controls", "visual_effect", "pitfalls", "pairs_with")

# A few real modules genuinely expose only two controls (velvia, haze removal,
# output color profile), so two is the floor rather than three.
MIN_CONTROLS = 2
MIN_FULL_WORDS = 250
MAX_FULL_WORDS = 900
MIN_STUB_WORDS = 25


def check_doc(doc: ModuleDoc) -> list[str]:
    """Return a list of violation messages for one entry."""
    problems: list[str] = []
    name = doc.path.name
    stem = doc.path.stem

    if doc.op != stem:
        problems.append(f"header op {doc.op!r} does not match filename {name!r}")
    if doc.op not in KNOWN_OPS:
        problems.append(f"op {doc.op!r} is not in the known-ops list")
    if not doc.display_name.strip():
        problems.append("empty display name in header")

    for section in REQUIRED_SECTIONS:
        if not doc.sections.get(section):
            problems.append(f"missing or empty required section {section!r}")

    if doc.is_full:
        for section in FULL_SECTIONS:
            if not doc.sections.get(section):
                problems.append(f"full entry missing section {section!r}")
        bullets = [
            line
            for line in doc.text.splitlines()
            if line.startswith("- ") and _in_key_controls(doc.text, line)
        ]
        if len(bullets) < MIN_CONTROLS:
            problems.append(
                f"full entry has {len(bullets)} key_controls bullets, "
                f"need at least {MIN_CONTROLS}"
            )
        visual = doc.sections.get("visual_effect", "")
        if "BEFORE" not in visual or "AFTER" not in visual:
            problems.append("visual_effect must contain BEFORE: and AFTER:")
        if not MIN_FULL_WORDS <= doc.word_count <= MAX_FULL_WORDS:
            problems.append(
                f"full entry word count {doc.word_count} outside "
                f"[{MIN_FULL_WORDS}, {MAX_FULL_WORDS}]"
            )
    else:
        if doc.word_count < MIN_STUB_WORDS:
            problems.append(f"stub entry is too short ({doc.word_count} words)")
        for section in FULL_SECTIONS:
            if section in doc.sections:
                problems.append(
                    f"stub entry has {section!r} but no key_controls -- "
                    "either complete it or drop the section"
                )

    return problems


def _in_key_controls(text: str, line: str) -> bool:
    """True if ``line`` sits inside the key_controls block of ``text``."""
    start = text.find("\nkey_controls:")
    if start < 0:
        return False
    tail = text[start:]
    for other in ("\nvisual_effect:", "\npitfalls:", "\npairs_with:"):
        end = tail.find(other)
        if end > 0:
            tail = tail[:end]
    return line in tail


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "corpus_dir",
        nargs="?",
        default=None,
        help="module library directory (default: helper/data/module_library)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args(argv)

    corpus_dir = (
        Path(args.corpus_dir)
        if args.corpus_dir
        else REPO_ROOT / "helper" / "data" / "module_library"
    )

    # Parse each file individually so a malformed header is reported with its
    # filename rather than aborting the whole run.
    docs: list[ModuleDoc] = []
    violations: dict[str, list[str]] = {}
    paths = [p for p in sorted(corpus_dir.glob("*.md")) if not p.name.startswith("_")]
    if not paths:
        print(f"ERROR: no module entries found in {corpus_dir}", file=sys.stderr)
        return 1
    for path in paths:
        try:
            docs.append(parse_module_file(path))
        except ValueError as exc:
            violations[path.name] = [str(exc)]

    for doc in docs:
        problems = check_doc(doc)
        if problems:
            violations[doc.path.name] = problems

    seen_ops: dict[str, str] = {}
    for doc in docs:
        if doc.op in seen_ops:
            violations.setdefault(doc.path.name, []).append(
                f"duplicate op {doc.op!r} (also in {seen_ops[doc.op]})"
            )
        seen_ops[doc.op] = doc.path.name

    full = [d for d in docs if d.is_full]
    stubs = [d for d in docs if d.is_stub]
    ops = {d.op for d in docs}

    missing_t1 = [op for op in TIER1_OPS if op not in ops]
    missing_t2 = [op for op in TIER2_OPS if op not in ops]
    stub_t1 = [op for op in TIER1_OPS if op in {d.op for d in stubs}]
    stub_t2 = [op for op in TIER2_OPS if op in {d.op for d in stubs}]

    if not args.quiet:
        print(f"module library: {corpus_dir}")
        print(f"  entries : {len(docs)}")
        print(f"  full    : {len(full)}")
        print(f"  stub    : {len(stubs)}")
        total_words = sum(d.word_count for d in docs)
        print(f"  words   : {total_words} (mean {total_words // max(len(docs), 1)})")
        print(f"  tier 1  : {len(TIER1_OPS) - len(missing_t1)}/{len(TIER1_OPS)} present")
        print(f"  tier 2  : {len(TIER2_OPS) - len(missing_t2)}/{len(TIER2_OPS)} present")
        if stubs:
            print("  stub entries: " + ", ".join(sorted(d.op for d in stubs)))

    # Tier 1/2 coverage is a hard requirement, but `clipping` is a deprecated
    # module the plan lists only as the legacy alias of crop, so a stub is fine.
    tier_stub_allowed = {"clipping"}
    for op in missing_t1:
        violations.setdefault("<coverage>", []).append(f"tier 1 op {op!r} has no entry")
    for op in missing_t2:
        violations.setdefault("<coverage>", []).append(f"tier 2 op {op!r} has no entry")
    for op in stub_t1 + stub_t2:
        if op not in tier_stub_allowed:
            violations.setdefault("<coverage>", []).append(
                f"tier 1/2 op {op!r} is only a stub; it must be a full entry"
            )

    if violations:
        print("\nVIOLATIONS", file=sys.stderr)
        for name in sorted(violations):
            for problem in violations[name]:
                print(f"  {name}: {problem}", file=sys.stderr)
        print(f"\n{sum(len(v) for v in violations.values())} problem(s)", file=sys.stderr)
        return 1

    if not args.quiet:
        print("\nOK: module library validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
