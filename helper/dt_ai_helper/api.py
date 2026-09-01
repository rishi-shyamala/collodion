"""HTTP route handlers implementing the helper API contract (plan §5.2).

Everything here reads shared state off ``request.app.state`` (set up by
``main.create_app``) rather than via constructor injection, so later workers
can add routes to this same router with a small diff instead of threading
new parameters through a factory function.

Seam for other workers
-----------------------
``/chat`` enqueues a job of kind ``"chat"`` whose handler is
``run_chat_job`` below. It now runs the real pipeline: RAG retrieval,
``image_context`` enrichment, server-side per-``history_id`` chat history,
and an ``llm.OpenAIChatClient`` call built from the active
``ConfigStore`` preset. Because job handlers only receive ``payload`` (see
``jobs.JobManager``), ``run_chat_job`` additionally takes the owning
``FastAPI`` app so it can reach ``app.state.config_store`` /
``app.state.chat_histories`` -- ``main.create_app`` registers it via a small
closure that supplies ``app`` (see the comment there). Likewise
``/optimize``, ``/vision``, and ``/style`` (owned by other workers) can be
added to this same ``router`` following the ``/chat`` pattern: validate a
pydantic body, call ``request.app.state.job_manager.submit(<kind>,
payload)``, return ``{"job_id": job_id}``.

History clearing: ``POST /history/clear`` with ``{"history_id": ...}`` wipes
one per-image history server-side (rather than a ``clear`` flag on
``ChatRequest``) so Lua's "Clear" button can fire it independently of
sending a message; document this alongside plan §5.2 if the contract there
is amended.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dt_ai_helper import __version__, context, histogram, prompts, rag
from dt_ai_helper import styles as styles_module
from dt_ai_helper.llm import (
    LLMError,
    OpenAIChatClient,
    build_vision_content,
    guard_vision_upload,
)

router = APIRouter()

#: Default LLM sampling parameters for chat turns. Not yet user-configurable
#: (no field for it in plan §5.2's /config body) -- revisit if a worker adds
#: per-preset generation settings.
CHAT_TEMPERATURE = 0.4
CHAT_MAX_TOKENS = 900

#: Number of RAG module-library files injected per chat turn (plan §5.5).
CHAT_RAG_TOP_K = 4

#: history_id fallback when Lua omits one (defensive; Lua is expected to key
#: this per-image per plan §5.3).
DEFAULT_HISTORY_ID = "default"

#: Chat history is trimmed to roughly this many characters (summed across
#: stored turns) before being sent back to the model, per plan §5.3.
DEFAULT_HISTORY_CHAR_BUDGET = 8000


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    config: ConfigStore = request.app.state.config_store
    return {
        "status": "ok",
        "version": __version__,
        "model_ready": config.model_ready(),
    }


# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------


class ModelPreset(BaseModel):
    """A single named model preset (plan §5.2 POST /config body)."""

    name: str
    base_url: str
    api_key: str | None = None
    model: str
    supports_vision: bool = False


class ConfigStore:
    """In-memory preset store.

    Not persisted across restarts by design (the skeleton has no notion of a
    settings file yet; the Lua side re-sends presets on connect). Holds
    multiple named presets plus which one is "active".
    """

    def __init__(self) -> None:
        self._presets: dict[str, ModelPreset] = {}
        self._active: str | None = None

    def upsert(self, preset: ModelPreset) -> None:
        self._presets[preset.name] = preset
        if self._active is None:
            self._active = preset.name

    def active_preset(self) -> ModelPreset | None:
        if self._active is None:
            return None
        return self._presets.get(self._active)

    def model_ready(self) -> bool:
        preset = self.active_preset()
        return bool(preset and preset.base_url and preset.model)

    def to_public_dict(self) -> dict[str, Any]:
        """Redact api_key for every preset (plan: "api_key redacted")."""
        presets = {}
        for name, preset in self._presets.items():
            data = preset.model_dump()
            if data.get("api_key"):
                data["api_key"] = "***"
            presets[name] = data
        return {"active": self._active, "presets": presets}


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    config: ConfigStore = request.app.state.config_store
    return config.to_public_dict()


@router.post("/config")
async def set_config(preset: ModelPreset, request: Request) -> dict[str, Any]:
    config: ConfigStore = request.app.state.config_store
    config.upsert(preset)
    return config.to_public_dict()


# ---------------------------------------------------------------------------
# /heartbeat
# ---------------------------------------------------------------------------


@router.post("/heartbeat")
async def heartbeat(request: Request) -> dict[str, Any]:
    request.app.state.last_heartbeat = time.time()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /chat + /jobs/{id} + /history/clear
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    history_id: str | None = None
    image_context: dict[str, Any] | None = Field(default=None)


class NoActivePresetError(RuntimeError):
    """Raised by ``run_chat_job`` when no model preset is configured.

    Surfaced to the client as the job's ``error`` field (``JobManager``
    catches handler exceptions and stores ``str(exc)``), satisfying the
    "if no preset configured, return a helpful error" requirement without a
    special-cased response shape.
    """


class ChatHistoryStore:
    """Server-side chat history, keyed by ``history_id`` (plan §5.3).

    One history per image (Lua is expected to key ``history_id`` off the
    image, e.g. its path or db id); trimmed to a character budget on every
    append so a long-running chat never grows the prompt unboundedly.
    """

    def __init__(self, char_budget: int = DEFAULT_HISTORY_CHAR_BUDGET) -> None:
        self._char_budget = char_budget
        self._histories: dict[str, list[dict[str, str]]] = {}

    def get(self, history_id: str) -> list[dict[str, str]]:
        """A copy of the stored turns for ``history_id`` (oldest first)."""
        return list(self._histories.get(history_id, []))

    def append_turn(self, history_id: str, user_message: str, answer: str) -> None:
        turns = self._histories.setdefault(history_id, [])
        turns.append({"role": "user", "content": user_message})
        turns.append({"role": "assistant", "content": answer})
        self._trim(turns)

    def _trim(self, turns: list[dict[str, str]]) -> None:
        total = sum(len(t["content"]) for t in turns)
        # Always keep at least the most recent exchange, even if it alone
        # exceeds the budget -- dropping the question just asked would be
        # worse than a slightly oversized prompt.
        while total > self._char_budget and len(turns) > 2:
            removed = turns.pop(0)
            total -= len(removed["content"])

    def clear(self, history_id: str) -> None:
        self._histories.pop(history_id, None)


def _build_llm_client(preset: ModelPreset, *, allow_upload: bool = False) -> OpenAIChatClient:
    return OpenAIChatClient(
        base_url=preset.base_url,
        api_key=preset.api_key,
        model=preset.model,
        supports_vision=preset.supports_vision,
        allow_upload=allow_upload,
    )


async def run_chat_job(payload: dict[str, Any], app: Any) -> dict[str, Any]:
    """Job handler for kind ``"chat"``.

    Pipeline (plan §5.2/§5.3/§5.5): resolve the active preset (error out
    with a helpful message if none is configured), enrich ``image_context``
    via ``context.py`` into a ``CURRENT EDIT STATE`` block when present,
    retrieve the top-``CHAT_RAG_TOP_K`` module-library excerpts for the
    user's message, assemble messages with the trimmed per-``history_id``
    history, call the LLM, then record the turn. Return shape
    (``{"answer": str, "style": {...} | None}``) is the contract the Lua
    transcript rendering is built against.

    ``app`` is the owning ``FastAPI`` app (see ``main.create_app``'s
    registration closure) -- job handlers otherwise only see ``payload``.
    """
    config: ConfigStore = app.state.config_store
    preset = config.active_preset()
    if preset is None or not config.model_ready():
        raise NoActivePresetError(
            "No model preset is configured yet. Add one via the model "
            "preset picker (or POST /config) before chatting."
        )

    message = payload.get("message", "")
    history_id = payload.get("history_id") or DEFAULT_HISTORY_ID
    raw_image_context = payload.get("image_context")

    edit_state_block: str | None = None
    if raw_image_context:
        enriched = context.build_image_context(
            raw_image_context,
            db_path=raw_image_context.get("db_path"),
            image_id=raw_image_context.get("image_id"),
        )
        edit_state_block = context.render_edit_state_block(enriched)

    retriever = rag.get_retriever()
    retrieved_text = retriever.retrieve_text(message, k=CHAT_RAG_TOP_K)
    module_library_block = f"MODULE LIBRARY\n\n{retrieved_text}" if retrieved_text else None

    history_store: ChatHistoryStore = app.state.chat_histories
    history = history_store.get(history_id)

    messages = prompts.build_chat_messages(
        user_message=message,
        history=history,
        edit_state_block=edit_state_block,
        module_library_block=module_library_block,
    )

    client = _build_llm_client(preset)
    try:
        answer = await client.chat(
            messages, temperature=CHAT_TEMPERATURE, max_tokens=CHAT_MAX_TOKENS
        )
    except LLMError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    finally:
        await client.aclose()

    history_store.append_turn(history_id, message, answer)
    return {"answer": answer, "style": None}


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> dict[str, Any]:
    job_manager = request.app.state.job_manager
    job_id = job_manager.submit("chat", body.model_dump())
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, Any]:
    job_manager = request.app.state.job_manager
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_public_dict()


class HistoryClearRequest(BaseModel):
    history_id: str


@router.post("/history/clear")
async def clear_history(body: HistoryClearRequest, request: Request) -> dict[str, Any]:
    history_store: ChatHistoryStore = request.app.state.chat_histories
    history_store.clear(body.history_id)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /style
# ---------------------------------------------------------------------------
#
# Deviation from the literal plan §5.2 contract (`{recommendation_id} ->
# {file}`): per this feature's task spec, the request carries the
# structured recommendation (plan §5.5's `{"recommendations": [...]}`)
# directly rather than a ``recommendation_id`` referencing a prior job's
# stored output, and the response is the richer
# `{file, included_ops, skipped_ops, manual_steps}` shape rather than bare
# `{file}` - this needs no job/history-store plumbing on either side and
# still fits the same seam other workers' job handlers use. Noted here and
# in the PR description; flag if a stored-recommendation flow turns out to
# be needed later.


class StyleRequest(BaseModel):
    recommendation: dict[str, Any]
    name: str | None = None


def _manual_step(entry: dict[str, Any]) -> str:
    module = entry.get("module") or entry.get("op") or "?"
    control = entry.get("control")
    reason = entry.get("reason", "not included")
    if control:
        return f"{module}: could not set '{control}' automatically ({reason}) - set it manually."
    return f"{module}: not included in the style ({reason}) - apply manually if desired."


def _style_from_recommendation(
    recommendation: dict[str, Any],
    name: str,
    style_dir: Path | None,
) -> dict[str, Any]:
    """Shared build path for ``/style`` and ``/optimize``'s style-from-job step.

    Returns the same ``{file, included_ops, skipped_ops, manual_steps}``
    shape ``POST /style`` has always returned -- extracted so
    ``run_optimize_job`` can build a style from its own freshly-produced
    recommendation without re-POSTing to itself or duplicating the
    translate/build/write sequence.
    """
    modules, translate_skipped = styles_module.translate_recommendation(recommendation)
    result = styles_module.build_style(name, modules)

    skipped_ops = [
        {"module": s["op"], "control": None, "reason": s["reason"]}
        for s in result["skipped_ops"]
    ] + translate_skipped

    path = styles_module.write_style_file(result["xml"], name, style_dir)

    return {
        "file": str(path),
        "included_ops": result["included_ops"],
        "skipped_ops": skipped_ops,
        "manual_steps": [_manual_step(s) for s in skipped_ops],
    }


@router.post("/style")
async def create_style(body: StyleRequest, request: Request) -> dict[str, Any]:
    name = body.name or f"ai-assistant/style-{int(time.time())}"
    style_dir: Path | None = getattr(request.app.state, "style_dir", None)
    return _style_from_recommendation(body.recommendation, name, style_dir)


# ---------------------------------------------------------------------------
# /optimize
# ---------------------------------------------------------------------------
#
# Plan §5.2/§5.5/§6, Phase 3 (this worker's scope): histogram+metadata
# analysis -> deterministic issue tags -> RAG retrieval for those tags ->
# strict-JSON LLM recommendation -> readable transcript text + a
# server-built .dtstyle for the encodable subset. Per
# documentation/agent-insights/001-orchestration-log.md's integration note
# from W7 (styles), the job result carries ``style.file`` because Lua's
# Apply-style button expects it there.


class OptimizeRequest(BaseModel):
    image_context: dict[str, Any] | None = Field(default=None)
    preview_path: str


#: Sampling params for the optimize LLM call. Kept separate from chat's
#: constants (a structured-JSON call benefits from a slightly larger token
#: budget and a lower temperature for consistent module/control naming).
OPTIMIZE_TEMPERATURE = 0.2
OPTIMIZE_MAX_TOKENS = 1200

#: Number of RAG module-library files injected per optimize call.
OPTIMIZE_RAG_TOP_K = 4


class PreviewNotFoundError(RuntimeError):
    """Raised when ``preview_path`` doesn't exist on disk."""


def _read_exif(image_context: dict[str, Any] | None) -> dict[str, Any]:
    return (image_context or {}).get("exif") or {}


def _render_histogram_summary(stats: dict[str, Any]) -> str:
    """Compact, LLM-facing summary of histogram.compute_stats' output.

    Deliberately omits the 256-bin histograms themselves (the LLM has no
    use for raw bin counts) and keeps to the numbers the rule layer and a
    human editor actually reason about.
    """
    luma = stats.get("luma", {})
    wb = stats.get("wb_hint", {})
    lines = [
        "HISTOGRAM STATISTICS (from a display-referred sRGB preview export "
        "-- approximate, not scene-referred)",
        f"size: {stats.get('width')}x{stats.get('height')}",
        f"mean luma: {luma.get('mean', 0):.1f}/255",
        f"luma percentiles: p1={luma.get('p1', 0):.1f} p5={luma.get('p5', 0):.1f} "
        f"p50={luma.get('p50', 0):.1f} p95={luma.get('p95', 0):.1f} "
        f"p99={luma.get('p99', 0):.1f}",
        f"clipped: {stats.get('clipped_black_pct', 0):.2f}% black, "
        f"{stats.get('clipped_white_pct', 0):.2f}% white",
        f"dynamic range utilization: {stats.get('dynamic_range_score', 0):.1f}/100",
        f"mean saturation (HSV): {stats.get('mean_saturation', 0):.1f}/100",
        f"gray-world white balance ratios: R/G={wb.get('r_g_ratio', 1.0):.3f} "
        f"B/G={wb.get('b_g_ratio', 1.0):.3f}",
        f"noise proxy (shadow high-frequency stddev): {stats.get('noise_proxy', 0):.2f}",
    ]
    return "\n".join(lines)


def _render_exif_summary(exif: dict[str, Any]) -> str:
    if not exif:
        return "EXIF\n\n(none provided)"
    bits = ", ".join(f"{k}={v}" for k, v in exif.items() if v is not None)
    return f"EXIF\n\n{bits}" if bits else "EXIF\n\n(none provided)"


async def run_optimize_job(payload: dict[str, Any], app: Any) -> dict[str, Any]:
    """Job handler for kind ``"optimize"`` (plan §5.2/§5.5/§6).

    Pipeline: resolve the active preset; enrich ``image_context`` (same
    ``context.py`` path as chat); compute histogram stats + deterministic
    issue tags from ``preview_path``; synthesize a RAG query from those
    tags and retrieve MODULE LIBRARY excerpts; call the LLM in
    ``chat_json`` (strict JSON) mode; render the structured recommendation
    as readable transcript text; build a ``.dtstyle`` for whatever subset
    of the recommendation is encodable. Returns
    ``{"answer": str, "style": {"file", "summary"} | None,
    "recommendation": dict}``.
    """
    config: ConfigStore = app.state.config_store
    preset = config.active_preset()
    if preset is None or not config.model_ready():
        raise NoActivePresetError(
            "No model preset is configured yet. Add one via the model "
            "preset picker (or POST /config) before running Optimize."
        )

    preview_path = payload.get("preview_path")
    if not preview_path or not Path(preview_path).is_file():
        raise PreviewNotFoundError(
            f"preview image not found at {preview_path!r}; export a preview before "
            "running Optimize"
        )

    raw_image_context = payload.get("image_context") or {}
    enriched_context: dict[str, Any] = {}
    if raw_image_context:
        enriched_context = context.build_image_context(
            raw_image_context,
            db_path=raw_image_context.get("db_path"),
            image_id=raw_image_context.get("image_id"),
        )
    edit_state_block = context.render_edit_state_block(enriched_context)

    exif = _read_exif(raw_image_context)
    enabled_modules = enriched_context.get("enabled_modules") or []

    analysis = histogram.analyze(preview_path, exif=exif, enabled_modules=enabled_modules)
    stats = analysis["stats"]
    issue_tags = analysis["issue_tags"]

    retriever = rag.get_retriever()
    retrieval_query = prompts.optimize_retrieval_query(issue_tags)
    retrieved_text = retriever.retrieve_text(retrieval_query, k=OPTIMIZE_RAG_TOP_K)
    module_library_block = f"MODULE LIBRARY\n\n{retrieved_text}" if retrieved_text else None

    messages = prompts.build_optimize_messages(
        histogram_summary=_render_histogram_summary(stats),
        exif_summary=_render_exif_summary(exif),
        issue_tags=issue_tags,
        edit_state_block=edit_state_block,
        module_library_block=module_library_block,
    )

    client = _build_llm_client(preset)
    try:
        recommendation = await client.chat_json(
            messages, temperature=OPTIMIZE_TEMPERATURE, max_tokens=OPTIMIZE_MAX_TOKENS
        )
    except LLMError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc
    finally:
        await client.aclose()

    answer = prompts.render_recommendation_text(recommendation)

    style: dict[str, Any] | None = None
    if recommendation.get("recommendations"):
        style_dir: Path | None = getattr(app.state, "style_dir", None)
        style_name = f"ai-assistant/optimize-{int(time.time())}"
        style_result = _style_from_recommendation(recommendation, style_name, style_dir)
        if style_result["included_ops"]:
            included_ops = style_result["included_ops"]
            included = ", ".join(included_ops)
            summary = f"Built a style with {len(included_ops)} module(s): {included}."
            if style_result["manual_steps"]:
                summary += f" {len(style_result['manual_steps'])} step(s) need manual application."
            style = {"file": style_result["file"], "summary": summary}

    return {"answer": answer, "style": style, "recommendation": recommendation}


@router.post("/optimize")
async def optimize(body: OptimizeRequest, request: Request) -> dict[str, Any]:
    job_manager = request.app.state.job_manager
    job_id = job_manager.submit("optimize", body.model_dump())
    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# /vision
# ---------------------------------------------------------------------------
#
# Deviation from the literal plan §5.2 contract (`{message?, image_context?,
# preview_path} -> {job_id}`): per this feature's task spec, the request
# also carries `allow_upload: bool` -- Lua's "allow image upload to cloud
# endpoints" preference (plan §5.1) -- because the privacy gate
# (`llm.guard_vision_upload`, plan §5.4/§11: "never send the image unless
# ... (endpoint is localhost OR the allow-upload pref is on)") has to be
# evaluated per-request against whichever preset is active, and the helper
# has no other channel for that pref today (`ConfigStore`/`ModelPreset`
# only carries per-endpoint capability flags, not this user-level consent
# toggle). Noted here and in the PR description.


class VisionRequest(BaseModel):
    message: str | None = None
    image_context: dict[str, Any] | None = Field(default=None)
    preview_path: str
    allow_upload: bool = False


#: Sampling params for vision's two passes (plan §5.5's describe/recommend).
VISION_TEMPERATURE = 0.4
VISION_DESCRIBE_MAX_TOKENS = 500
VISION_RECOMMEND_MAX_TOKENS = 900

#: Number of RAG module-library files injected into the recommend pass,
#: retrieved against pass 1's own description (plan §5.5: "keeps retrieval
#: relevant").
VISION_RAG_TOP_K = 4


class VisionNotSupportedError(RuntimeError):
    """Raised when the active preset's ``supports_vision`` flag is false."""


async def run_vision_job(payload: dict[str, Any], app: Any) -> dict[str, Any]:
    """Job handler for kind ``"vision"`` (plan §5.2/§5.5, two-pass).

    Pass 1 ("describe"): a vision call (image + text) asking the model to
    describe the photo -- gated by ``llm.guard_vision_upload`` using the
    active preset's ``base_url`` and this request's ``allow_upload`` flag,
    checked *before* any image bytes are read or any client is built, so a
    refusal never gets close to constructing a payload that would leak the
    image. Pass 2 ("recommend"): a text-only call that maps pass 1's own
    description onto MODULE LIBRARY excerpts retrieved for whatever issues
    it named. Also refuses with a clear error (not a crash) when the active
    preset's ``supports_vision`` flag is false. Returns
    ``{"answer": str, "style": None, "description": str}``.
    """
    config: ConfigStore = app.state.config_store
    preset = config.active_preset()
    if preset is None or not config.model_ready():
        raise NoActivePresetError(
            "No model preset is configured yet. Add one via the model "
            "preset picker (or POST /config) before running Analyze image."
        )

    if not preset.supports_vision:
        raise VisionNotSupportedError(
            f"The active model preset {preset.name!r} is not marked as "
            "vision-capable. Pick a vision-capable preset before running "
            "Analyze image."
        )

    allow_upload = bool(payload.get("allow_upload", False))
    # Check the privacy gate up front (plan §5.4/§11) -- fail before
    # reading the preview off disk or opening any connection, not after.
    guard_vision_upload(base_url=preset.base_url, allow_upload=allow_upload)

    preview_path = payload.get("preview_path")
    if not preview_path or not Path(preview_path).is_file():
        raise PreviewNotFoundError(
            f"preview image not found at {preview_path!r}; export a preview before "
            "running Analyze image"
        )
    try:
        image_bytes = Path(preview_path).read_bytes()
    except OSError as exc:
        raise PreviewNotFoundError(
            f"could not read preview image at {preview_path!r}: {exc}"
        ) from exc

    message = payload.get("message")
    raw_image_context = payload.get("image_context")
    edit_state_block: str | None = None
    if raw_image_context:
        enriched = context.build_image_context(
            raw_image_context,
            db_path=raw_image_context.get("db_path"),
            image_id=raw_image_context.get("image_id"),
        )
        edit_state_block = context.render_edit_state_block(enriched)

    describe_messages = prompts.build_vision_describe_messages(
        user_message=message, edit_state_block=edit_state_block
    )
    describe_text = describe_messages[-1]["content"]
    describe_messages[-1]["content"] = build_vision_content(
        describe_text, image_bytes, base_url=preset.base_url, allow_upload=allow_upload
    )

    client = _build_llm_client(preset, allow_upload=allow_upload)
    try:
        try:
            description = await client.chat(
                describe_messages,
                temperature=VISION_TEMPERATURE,
                max_tokens=VISION_DESCRIBE_MAX_TOKENS,
                is_vision_request=True,
            )
        except LLMError as exc:
            raise RuntimeError(f"LLM request failed (describe pass): {exc}") from exc

        retriever = rag.get_retriever()
        retrieved_text = retriever.retrieve_text(description, k=VISION_RAG_TOP_K)
        module_library_block = f"MODULE LIBRARY\n\n{retrieved_text}" if retrieved_text else None

        recommend_messages = prompts.build_vision_recommend_messages(
            description=description, module_library_block=module_library_block
        )
        try:
            answer = await client.chat(
                recommend_messages,
                temperature=VISION_TEMPERATURE,
                max_tokens=VISION_RECOMMEND_MAX_TOKENS,
            )
        except LLMError as exc:
            raise RuntimeError(f"LLM request failed (recommend pass): {exc}") from exc
    finally:
        await client.aclose()

    return {"answer": answer, "style": None, "description": description}


@router.post("/vision")
async def vision(body: VisionRequest, request: Request) -> dict[str, Any]:
    job_manager = request.app.state.job_manager
    job_id = job_manager.submit("vision", body.model_dump())
    return {"job_id": job_id}
