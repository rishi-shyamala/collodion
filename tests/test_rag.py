"""Offline tests for the RAG module library and retriever (plan section 8).

Nothing here touches the network: the corpus is on disk and BM25 is local.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from dt_ai_helper.rag import (
    DEFAULT_TOP_K,
    SYNONYMS,
    BM25Retriever,
    ModuleDoc,
    RetrievalResult,
    Retriever,
    default_corpus_dir,
    expand_query,
    format_context,
    get_retriever,
    load_corpus,
    parse_module_file,
    tokenize,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "helper" / "data" / "module_library"


def _load_build_library():
    """Import scripts/build_library.py without making scripts/ a package."""
    path = REPO_ROOT / "scripts" / "build_library.py"
    spec = importlib.util.spec_from_file_location("build_library", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_library"] = module
    spec.loader.exec_module(module)
    return module


build_library = _load_build_library()


@pytest.fixture(scope="module")
def docs() -> list[ModuleDoc]:
    return load_corpus(CORPUS_DIR)


@pytest.fixture(scope="module")
def retriever() -> BM25Retriever:
    return BM25Retriever(corpus_dir=CORPUS_DIR)


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


def test_default_corpus_dir_is_the_shipped_library():
    assert default_corpus_dir() == CORPUS_DIR


def test_corpus_validates_against_build_library():
    """scripts/build_library.py is the corpus contract; it must pass."""
    assert build_library.main([str(CORPUS_DIR), "--quiet"]) == 0


def test_corpus_size_and_shape(docs: list[ModuleDoc]):
    assert len(docs) >= 85, "the plan calls for ~90 module files"
    full = [d for d in docs if d.is_full]
    stubs = [d for d in docs if d.is_stub]
    assert len(full) >= 40
    assert len(stubs) >= 20
    assert len(full) + len(stubs) == len(docs)


def test_every_filename_matches_its_header_op(docs: list[ModuleDoc]):
    for doc in docs:
        assert doc.op == doc.path.stem
        assert doc.op in build_library.KNOWN_OPS


def test_metadata_files_are_excluded(docs: list[ModuleDoc]):
    assert (CORPUS_DIR / "_SOURCES.md").exists(), "attribution file must ship"
    assert all(not d.path.name.startswith("_") for d in docs)


def test_tier1_and_tier2_modules_are_full_entries(docs: list[ModuleDoc]):
    by_op = {d.op: d for d in docs}
    # `clipping` is the deprecated crop-and-rotate alias; a stub is acceptable.
    tier_ops = [
        op
        for op in build_library.TIER1_OPS + build_library.TIER2_OPS
        if op != "clipping"
    ]
    for op in tier_ops:
        assert op in by_op, f"tier 1/2 module {op} is missing from the corpus"
        assert by_op[op].is_full, f"tier 1/2 module {op} must be a full entry"
        assert by_op[op].word_count >= 250


def test_full_entries_carry_the_whole_template(docs: list[ModuleDoc]):
    for doc in (d for d in docs if d.is_full):
        for section in ("purpose", "use_when", "key_controls", "visual_effect"):
            assert doc.sections.get(section), f"{doc.op} missing {section}"
        assert "BEFORE" in doc.sections["visual_effect"]
        assert "AFTER" in doc.sections["visual_effect"]


def test_stub_entries_are_header_purpose_use_when(docs: list[ModuleDoc]):
    for doc in (d for d in docs if d.is_stub):
        assert doc.sections.get("purpose")
        assert doc.sections.get("use_when")
        assert "key_controls" not in doc.sections


def test_deprecated_modules_are_flagged(docs: list[ModuleDoc]):
    by_op = {d.op: d for d in docs}
    for op in ("invert", "spots", "levels", "clipping", "colorbalance"):
        assert by_op[op].is_deprecated, f"{op} should be flagged deprecated"
    assert not by_op["filmicrgb"].is_deprecated


def test_parse_rejects_a_bad_header(tmp_path: Path):
    bad = tmp_path / "nonsense.md"
    bad.write_text("not a header\npurpose: x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_module_file(bad)


def test_load_corpus_rejects_a_missing_directory(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_corpus(tmp_path / "does-not-exist")


def test_load_corpus_rejects_an_empty_directory(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_corpus(tmp_path)


def test_build_library_reports_violations(tmp_path: Path):
    (tmp_path / "notamodule.md").write_text(
        "# not a module (notamodule)\ngroup: x\nsynonyms: y\n"
        "purpose: p\nuse_when: u\n",
        encoding="utf-8",
    )
    assert build_library.main([str(tmp_path), "--quiet"]) == 1


# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("White Balance: too WARM!") == ["white", "balance", "too", "warm"]


def test_expand_query_keeps_the_original_tokens():
    tokens = expand_query("wb is off")
    assert tokens[:3] == ["wb", "is", "off"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("wb", "temperature"),
        ("clarity please", "diffuse"),
        ("clarity please", "contrastntexture"),
        ("show me the curves", "tonecurve"),
        ("i want an hdr look", "filmicrgb"),
        ("i want an hdr look", "equalizer"),
    ],
)
def test_synonym_map_expands_photographer_vocabulary(query: str, expected: str):
    assert expected in expand_query(query)


def test_expansions_are_deduplicated():
    tokens = expand_query("white balance wb temperature")
    assert len(tokens) == len(set(tokens))


def test_synonym_map_has_no_empty_expansions():
    for key, values in SYNONYMS.items():
        assert values, f"synonym {key!r} expands to nothing"
        assert all(v == v.lower() and " " not in v for v in values), key


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


#: (query, op that must appear, maximum acceptable rank)
EXPECTED_HITS = [
    ("white balance too warm", "temperature", 1),
    ("wb is off in this shot", "temperature", 2),
    ("the sky is blown out", "highlights", 2),
    ("the sky is blown out", "filmicrgb", 3),
    ("make it punchier", "colorbalancergb", 2),
    ("add clarity", "contrastntexture", 3),
    ("how do I remove noise at high iso", "denoiseprofile", 4),
    ("the image is too dark", "exposure", 1),
    ("shadows are too dark and the sky is too bright", "toneequal", 4),
    ("the horizon is crooked", "ashift", 1),
    ("this building is leaning backwards", "ashift", 1),
    ("fix barrel distortion", "lens", 1),
    ("crop to 16:9", "crop", 1),
    ("dust spots in the sky", "retouch", 1),
    ("purple fringing on the branches", "cacorrectrgb", 1),
    ("convert to black and white", "monochrome", 2),
    ("remove haze from the distant hills", "hazeremoval", 1),
    ("darken the corners", "vignette", 1),
    ("add a film grain look", "grain", 1),
    ("blur out a face for privacy", "censorize", 1),
    ("i scanned a film negative", "negadoctor", 2),
    ("sharpen the image", "sharpen", 2),
    ("curves", "tonecurve", 2),
    ("hdr look", "filmicrgb", 2),
]


@pytest.mark.parametrize(("query", "op", "max_rank"), EXPECTED_HITS)
def test_representative_queries_hit_expected_modules(
    retriever: BM25Retriever, query: str, op: str, max_rank: int
):
    ops = [r.doc.op for r in retriever.retrieve(query)]
    assert op in ops[:max_rank], f"{query!r} -> {ops}"


#: Modules any reasonable answer to a "more contrast/punch" question may name.
CONTRAST_OPS = {
    "colorbalancergb",
    "bilat",
    "atrous",
    "contrastntexture",
    "tonecurve",
    "rgbcurve",
    "rgblevels",
    "filmicrgb",
    "sigmoid",
    "basecurve",
    "diffuse",
}


@pytest.mark.parametrize(
    "query",
    [
        "make it punchier",
        "the image looks flat, add some contrast",
        "give it more pop",
        "the photo needs more punch",
    ],
)
def test_contrast_queries_land_on_contrast_modules(
    retriever: BM25Retriever, query: str
):
    ops = {r.doc.op for r in retriever.retrieve(query)}
    assert ops & CONTRAST_OPS, f"{query!r} -> {sorted(ops)}"


def test_default_top_k_is_four(retriever: BM25Retriever):
    assert DEFAULT_TOP_K == 4
    assert len(retriever.retrieve("white balance too warm")) == 4


def test_k_is_honoured(retriever: BM25Retriever):
    assert len(retriever.retrieve("sharpen", k=1)) == 1
    assert len(retriever.retrieve("sharpen", k=7)) == 7
    assert retriever.retrieve("sharpen", k=0) == []


def test_scores_are_descending(retriever: BM25Retriever):
    scores = [r.score for r in retriever.retrieve("blown highlights in the sky")]
    assert scores == sorted(scores, reverse=True)


def test_zero_scoring_documents_are_dropped(retriever: BM25Retriever):
    assert retriever.retrieve("zzzqqq unmatchable gibberish token") == []


def test_empty_query_returns_nothing(retriever: BM25Retriever):
    assert retriever.retrieve("") == []
    assert retriever.retrieve("!!!") == []


def test_naming_a_module_ranks_it_first(retriever: BM25Retriever):
    for op in ("filmicrgb", "toneequal", "negadoctor", "vignette"):
        assert retriever.retrieve(f"what does {op} do")[0].doc.op == op


def test_deprecated_modules_do_not_outrank_replacements(retriever: BM25Retriever):
    ops = [r.doc.op for r in retriever.retrieve("i scanned a film negative")]
    assert ops.index("negadoctor") < ops.index("invert")


def test_deprecated_modules_remain_retrievable(retriever: BM25Retriever):
    ops = [r.doc.op for r in retriever.retrieve("what is the zone system module")]
    assert "zonesystem" in ops


def test_format_context_injects_entries_verbatim(retriever: BM25Retriever):
    results = retriever.retrieve("white balance too warm", k=2)
    context = format_context(results)
    for result in results:
        assert result.doc.text.strip() in context
    assert context.count("\n---\n") == 1


def test_retrieve_text_matches_format_context(retriever: BM25Retriever):
    query = "make it punchier"
    assert retriever.retrieve_text(query) == format_context(retriever.retrieve(query))


def test_get_retriever_is_cached():
    assert get_retriever(CORPUS_DIR) is get_retriever(CORPUS_DIR)


# ---------------------------------------------------------------------------
# Interface: an embedding backend must be able to replace BM25 later.
# ---------------------------------------------------------------------------


class _FakeEmbeddingRetriever(Retriever):
    """Stand-in proving the interface is all a caller depends on."""

    def __init__(self, docs: list[ModuleDoc]) -> None:
        self.docs = docs

    def retrieve(self, query: str, k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
        scored = [
            RetrievalResult(doc=d, score=float(len(set(tokenize(query)) & set(tokenize(d.op)))))
            for d in self.docs
        ]
        scored.sort(key=lambda r: -r.score)
        return scored[:k]


def test_an_alternative_backend_satisfies_the_interface(docs: list[ModuleDoc]):
    alt = _FakeEmbeddingRetriever(docs)
    assert isinstance(alt, Retriever)
    results = alt.retrieve("exposure", k=2)
    assert len(results) == 2
    assert results[0].doc.op == "exposure"
    assert alt.retrieve_text("exposure", k=1).startswith("# exposure (exposure)")


def test_retriever_is_abstract():
    with pytest.raises(TypeError):
        Retriever()  # type: ignore[abstract]
