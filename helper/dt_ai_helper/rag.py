"""RAG over the darktable module library (plan section 8).

The corpus lives in ``helper/data/module_library`` as one markdown file per
darktable processing module, named after the module's internal op name
(``filmicrgb.md``, ``colorbalancergb.md``, ...). Chunk granularity is the whole
file: the entries are small and are meant to be injected verbatim.

Retrieval is BM25 (``rank-bm25``) over the lowercased text of every file, with a
photographer-vocabulary synonym map applied to the query so that the words users
actually type ("wb", "clarity", "punchier", "blown out") reach the modules that
answer them. No embeddings and no vector store in v1 -- the corpus is small
enough that BM25 plus synonyms is sufficient, and it stays fully offline.

Everything sits behind the :class:`Retriever` interface so an embedding backend
can be dropped in later without touching callers.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from rank_bm25 import BM25Okapi

DEFAULT_TOP_K = 4

#: Files whose name starts with this prefix are metadata, not corpus entries.
_METADATA_PREFIX = "_"

#: Environment override for the corpus location (used by tests and packaging).
CORPUS_ENV_VAR = "DT_AI_HELPER_MODULE_LIBRARY"

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEADER_RE = re.compile(r"^#\s+(?P<display>.+?)\s+\((?P<op>[a-z0-9_]+)\)\s*$")

# ---------------------------------------------------------------------------
# Synonym map
# ---------------------------------------------------------------------------
# Keys are what a photographer types; values are terms that appear in the
# corpus. Multi-word keys are matched as substrings of the lowercased query,
# single-word keys are matched against query tokens. Expansions are appended to
# the query token list, so they add recall without removing the literal terms.
SYNONYMS: dict[str, list[str]] = {
    # --- white balance / colour temperature ---
    "wb": ["white", "balance", "temperature"],
    "white balance": ["temperature", "color", "calibration", "illuminant"],
    "too warm": ["temperature", "white", "balance", "cool", "kelvin"],
    "too orange": ["temperature", "white", "balance", "cast"],
    "too cool": ["temperature", "white", "balance", "warm", "kelvin"],
    "too blue": ["temperature", "white", "balance", "cast"],
    "color cast": ["temperature", "calibration", "illuminant", "tint"],
    "colour cast": ["temperature", "calibration", "illuminant", "tint"],
    "mixed lighting": ["calibration", "illuminant", "chromatic", "adaptation"],
    "tungsten": ["temperature", "illuminant", "kelvin"],
    "fluorescent": ["temperature", "illuminant", "tint"],
    # --- exposure / brightness ---
    "too dark": ["exposure", "brightness", "shadows", "underexposed"],
    "too bright": ["exposure", "highlights", "overexposed"],
    "underexposed": ["exposure", "brightness"],
    "overexposed": ["exposure", "highlights", "clipped"],
    "brighten": ["exposure", "brightness"],
    "darken": ["exposure", "brightness", "vignetting"],
    "ev": ["exposure", "stops"],
    "stops": ["exposure", "ev"],
    # --- highlights / shadows ---
    "blown out": ["highlights", "clipped", "reconstruction", "filmicrgb", "rolloff"],
    "blown": ["highlights", "clipped", "reconstruction", "filmicrgb"],
    "clipped": ["highlights", "reconstruction", "clipping"],
    "sky is blown": ["highlights", "reconstruction", "filmic", "rolloff", "clipped"],
    "recover highlights": ["highlights", "reconstruction", "filmic", "rolloff"],
    "magenta highlights": ["highlights", "reconstruction", "clipped"],
    "lift shadows": ["equalizer", "shadows", "tone", "exposure"],
    "open shadows": ["equalizer", "shadows", "tone"],
    "shadow detail": ["equalizer", "shadows", "tone"],
    "dodge and burn": ["equalizer", "tone", "dodge", "burn"],
    "dodging": ["equalizer", "tone", "dodge"],
    "burning": ["equalizer", "tone", "burn"],
    "backlit": ["equalizer", "tone", "shadows", "highlights"],
    "shadows are too dark": ["toneequal", "tone", "equalizer", "dodge", "shadows"],
    "sky too bright": ["toneequal", "graduatednd", "tone", "equalizer", "highlights"],
    "sky is too bright": ["toneequal", "graduatednd", "tone", "equalizer"],
    # --- tone mapping / look ---
    "hdr look": ["filmic", "filmicrgb", "tone", "equalizer", "dynamic", "range"],
    "hdr": ["filmic", "filmicrgb", "tone", "equalizer", "dynamic", "range"],
    "dynamic range": ["filmic", "filmicrgb", "sigmoid", "agx", "tone", "mapping"],
    "tone mapping": ["filmicrgb", "sigmoid", "agx", "basecurve"],
    "flat": ["contrast", "filmic", "curve", "local"],
    "washed out": ["contrast", "filmic", "saturation", "levels"],
    "film look": ["filmicrgb", "sigmoid", "agx", "grain", "colorchecker", "lut3d"],
    # --- contrast / punch ---
    "punchier": ["contrast", "colorbalancergb", "local", "saturation", "punch"],
    "punchy": ["contrast", "colorbalancergb", "local", "saturation", "punch"],
    "punch": ["contrast", "colorbalancergb", "local", "saturation"],
    "pop": ["contrast", "colorbalancergb", "local", "saturation", "punch"],
    "more contrast": ["contrast", "curve", "filmic", "colorbalancergb"],
    "curves": ["tonecurve", "rgbcurve", "curve"],
    "curve": ["tonecurve", "rgbcurve"],
    "s curve": ["tonecurve", "rgbcurve", "contrast"],
    "levels": ["rgblevels", "black", "white", "point"],
    "clarity": ["local", "contrast", "diffuse", "texture", "contrastntexture"],
    "micro contrast": ["local", "contrast", "atrous", "contrastntexture"],
    "local contrast": ["bilat", "atrous", "diffuse", "contrastntexture"],
    "structure": ["local", "contrast", "texture", "diffuse"],
    "depth": ["local", "contrast", "texture", "haze"],
    "definition": ["texture", "local", "contrast", "sharpen"],
    # --- sharpness / blur ---
    "soft": ["sharpen", "diffuse", "deblur", "blur"],
    "blurry": ["sharpen", "diffuse", "deblur"],
    "sharpen": ["sharpen", "diffuse", "atrous", "unsharp"],
    "sharpening": ["sharpen", "diffuse", "atrous", "unsharp"],
    "deblur": ["diffuse", "sharpen", "deblur"],
    "bokeh": ["blurs", "lens", "blur", "diaphragm"],
    "background blur": ["blurs", "lens", "blur", "mask"],
    "glow": ["bloom", "soften", "diffuse", "orton", "lowpass"],
    "dreamy": ["soften", "bloom", "diffuse", "orton"],
    # --- noise ---
    "noisy": ["denoise", "noise", "denoiseprofile"],
    "noise": ["denoise", "denoiseprofile", "rawdenoise", "nlmeans"],
    "grainy": ["denoise", "noise", "grain"],
    "high iso": ["denoise", "denoiseprofile", "noise"],
    "speckles": ["denoise", "hotpixels", "noise"],
    # --- colour work ---
    "saturation": ["colorbalancergb", "vibrance", "chroma", "velvia", "colorequal"],
    "saturated": ["colorbalancergb", "chroma", "saturation"],
    "vibrance": ["colorbalancergb", "vibrance", "chroma"],
    "colors are dull": ["saturation", "chroma", "colorbalancergb", "velvia"],
    "colours are dull": ["saturation", "chroma", "colorbalancergb", "velvia"],
    "more colorful": ["saturation", "chroma", "colorbalancergb", "vibrance"],
    "skin tone": ["colorequal", "colorzones", "calibration", "saturation", "skin"],
    "skin tones": ["colorequal", "colorzones", "calibration", "saturation", "skin"],
    "sky bluer": ["colorequal", "colorzones", "hue", "saturation", "blue"],
    "foliage": ["colorequal", "colorzones", "hue", "green"],
    "color grading": ["colorbalancergb", "rgbcurve", "lut3d", "colorchecker"],
    "colour grading": ["colorbalancergb", "rgbcurve", "lut3d", "colorchecker"],
    "teal and orange": ["colorbalancergb", "splittoning", "colorharmonizer"],
    "split tone": ["splittoning", "colorbalancergb"],
    "black and white": ["monochrome", "calibration", "gray", "channelmixerrgb"],
    "b&w": ["monochrome", "calibration", "gray", "channelmixerrgb"],
    "bw": ["monochrome", "calibration", "gray"],
    "sepia": ["splittoning", "colorize", "monochrome"],
    "lut": ["lut3d", "colorchecker", "cube"],
    "film simulation": ["lut3d", "colorchecker", "filmicrgb"],
    "purple fringing": ["cacorrectrgb", "chromatic", "aberration", "defringe"],
    "chromatic aberration": ["cacorrectrgb", "cacorrect", "lens", "aberration"],
    # --- geometry ---
    "crooked": ["ashift", "rotation", "straighten", "level"],
    "tilted": ["ashift", "rotation", "straighten", "level"],
    "straighten": ["ashift", "rotation", "level"],
    "level the horizon": ["ashift", "rotation", "horizon"],
    "converging verticals": ["ashift", "perspective", "keystone", "lens", "shift"],
    "keystone": ["ashift", "perspective", "lens", "shift"],
    "leaning buildings": ["ashift", "perspective", "keystone"],
    "distortion": ["lens", "distortion", "barrel", "pincushion"],
    "barrel": ["lens", "distortion"],
    "crop": ["crop", "aspect", "composition"],
    "aspect ratio": ["crop", "borders", "enlargecanvas", "aspect"],
    "dark corners": ["lens", "vignetting", "vignette"],
    # --- retouching / effects ---
    "dust spots": ["retouch", "spots", "heal", "clone"],
    "remove object": ["retouch", "heal", "clone", "liquify"],
    "blemish": ["retouch", "heal", "skin"],
    "smooth skin": ["retouch", "surface", "diffuse", "contrastntexture", "bilateral"],
    "vignette": ["vignetting", "vignette", "corners"],
    "border": ["borders", "framing", "enlargecanvas"],
    "frame": ["borders", "framing", "enlargecanvas"],
    "watermark": ["watermark", "logo", "signature"],
    "film grain": ["grain", "coarseness"],
    "blur a face": ["censorize", "pixellation", "anonymize"],
    "anonymize": ["censorize", "pixellation"],
    "haze": ["hazeremoval", "dehaze", "haze"],
    "hazy": ["hazeremoval", "dehaze", "contrast"],
    "foggy": ["hazeremoval", "dehaze"],
    "fog": ["hazeremoval", "dehaze"],
    # --- workflow / format ---
    "negative": ["negadoctor", "invert", "film", "scan"],
    "scan": ["negadoctor", "profile_gamma", "scan"],
    "export": ["colorout", "output", "profile", "srgb"],
    "srgb": ["colorout", "output", "profile"],
    "banding": ["dither", "posterize", "banding"],
    "moire": ["demosaic", "bilateral", "moire"],
    "mask": ["mask", "rasterfile", "drawn", "parametric"],
}

#: Longest-first so that "white balance" wins over "wb" style overlaps.
_PHRASE_KEYS: list[str] = sorted(
    (k for k in SYNONYMS if " " in k), key=len, reverse=True
)
_WORD_KEYS: dict[str, list[str]] = {k: v for k, v in SYNONYMS.items() if " " not in k}


def tokenize(text: str) -> list[str]:
    """Lowercase and split into alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


def expand_query(query: str) -> list[str]:
    """Tokenize ``query`` and append synonym expansions.

    Phrase keys are matched against the raw lowercased query; single-word keys
    are matched against its tokens. The original tokens are always kept.
    """
    lowered = query.lower()
    tokens = tokenize(lowered)
    expansions: list[str] = []
    for phrase in _PHRASE_KEYS:
        if phrase in lowered:
            expansions.extend(SYNONYMS[phrase])
    for token in tokens:
        if token in _WORD_KEYS:
            expansions.extend(_WORD_KEYS[token])
    seen = set(tokens)
    deduped: list[str] = []
    for token in expansions:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return tokens + deduped


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleDoc:
    """One module library file, loaded whole (chunk == file)."""

    op: str
    display_name: str
    path: Path
    text: str
    sections: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def is_full(self) -> bool:
        """True when the entry carries the full template, not just a stub."""
        return "key_controls" in self.sections

    @property
    def is_stub(self) -> bool:
        return not self.is_full

    @property
    def group(self) -> str:
        return self.sections.get("group", "")

    @property
    def is_deprecated(self) -> bool:
        """True for modules darktable marks deprecated or legacy.

        These are documented so the assistant can explain an old history stack,
        but they should not out-rank their modern replacements in retrieval.
        """
        return "deprecated" in self.group.lower()

    @property
    def synonyms(self) -> str:
        return self.sections.get("synonyms", "")

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class RetrievalResult:
    doc: ModuleDoc
    score: float


def default_corpus_dir() -> Path:
    """Location of the module library, overridable via the environment."""
    override = os.environ.get(CORPUS_ENV_VAR)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "module_library"


#: Section names the parser recognises as frontmatter-style header lines.
SECTION_KEYS = (
    "group",
    "synonyms",
    "purpose",
    "use_when",
    "do_not_combine",
    "key_controls",
    "visual_effect",
    "pitfalls",
    "pairs_with",
)


def parse_module_file(path: Path, text: str | None = None) -> ModuleDoc:
    """Parse one module markdown file into a :class:`ModuleDoc`.

    Raises ``ValueError`` if the ``# display name (op)`` header is missing or
    malformed -- ``scripts/build_library.py`` relies on this.
    """
    raw = path.read_text(encoding="utf-8") if text is None else text
    lines = raw.splitlines()
    if not lines:
        raise ValueError(f"{path}: file is empty")
    header = _HEADER_RE.match(lines[0])
    if header is None:
        raise ValueError(
            f"{path}: first line must be '# <display name> (<op>)', got {lines[0]!r}"
        )

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        key, sep, rest = stripped.partition(":")
        if sep and key in SECTION_KEYS and not line.startswith((" ", "\t", "-")):
            current = key
            sections[current] = [rest.strip()] if rest.strip() else []
        elif current is not None:
            sections[current].append(stripped)
    return ModuleDoc(
        op=header.group("op"),
        display_name=header.group("display"),
        path=path,
        text=raw,
        sections={k: " ".join(v).strip() for k, v in sections.items()},
    )


def load_corpus(corpus_dir: Path | str | None = None) -> list[ModuleDoc]:
    """Load every module entry from ``corpus_dir``, sorted by op name."""
    directory = Path(corpus_dir) if corpus_dir is not None else default_corpus_dir()
    if not directory.is_dir():
        raise FileNotFoundError(f"module library not found: {directory}")
    docs = [
        parse_module_file(p)
        for p in sorted(directory.glob("*.md"))
        if not p.name.startswith(_METADATA_PREFIX)
    ]
    if not docs:
        raise FileNotFoundError(f"module library is empty: {directory}")
    return docs


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class Retriever(ABC):
    """Minimal retrieval interface.

    An embedding-backed implementation can replace :class:`BM25Retriever`
    without any change to callers, as long as it honours this contract.
    """

    @abstractmethod
    def retrieve(self, query: str, k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
        """Return the ``k`` best-matching documents, best first."""

    def retrieve_text(self, query: str, k: int = DEFAULT_TOP_K) -> str:
        """Retrieve and format for verbatim injection into a prompt."""
        return format_context(self.retrieve(query, k=k))


class BM25Retriever(Retriever):
    """BM25 over whole files, with synonym-expanded queries.

    ``op_boost`` adds a flat score bonus when the query names a module's op name
    or display name outright, so "what does filmicrgb do" always returns
    ``filmicrgb.md`` first regardless of term statistics.

    ``deprecated_penalty`` scales down entries for modules darktable has
    deprecated. They stay retrievable (the assistant must be able to explain an
    old history stack) but should not out-rank their replacements: without it,
    "scanned film negative" returns ``invert`` above ``negadoctor``.
    """

    def __init__(
        self,
        docs: list[ModuleDoc] | None = None,
        *,
        corpus_dir: Path | str | None = None,
        op_boost: float = 5.0,
        deprecated_penalty: float = 0.45,
    ) -> None:
        self.docs = docs if docs is not None else load_corpus(corpus_dir)
        self.op_boost = op_boost
        self.deprecated_penalty = deprecated_penalty
        self._corpus_tokens = [tokenize(doc.text) for doc in self.docs]
        self._bm25 = BM25Okapi(self._corpus_tokens)
        self._name_tokens = [
            set(tokenize(doc.op)) | set(tokenize(doc.display_name)) for doc in self.docs
        ]

    def __len__(self) -> int:
        return len(self.docs)

    def retrieve(self, query: str, k: int = DEFAULT_TOP_K) -> list[RetrievalResult]:
        if k <= 0:
            return []
        tokens = expand_query(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        query_tokens = set(tokenize(query))
        ranked: list[RetrievalResult] = []
        for doc, score, names in zip(
            self.docs, scores, self._name_tokens, strict=True
        ):
            boosted = float(score)
            if doc.is_deprecated:
                boosted *= self.deprecated_penalty
            if names & query_tokens:
                boosted += self.op_boost
            ranked.append(RetrievalResult(doc=doc, score=boosted))
        ranked.sort(key=lambda r: (-r.score, r.doc.op))
        return [r for r in ranked[:k] if r.score > 0.0]


def format_context(results: list[RetrievalResult]) -> str:
    """Join retrieved entries verbatim, separated by a rule."""
    return "\n\n---\n\n".join(r.doc.text.strip() for r in results)


@lru_cache(maxsize=4)
def _cached_retriever(corpus_dir: str | None) -> BM25Retriever:
    return BM25Retriever(corpus_dir=corpus_dir)


def get_retriever(corpus_dir: Path | str | None = None) -> Retriever:
    """Process-wide cached retriever; loading the corpus is not free."""
    return _cached_retriever(str(corpus_dir) if corpus_dir is not None else None)
