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

from dt_ai_helper import __version__, context, prompts, rag
from dt_ai_helper import styles as styles_module
from dt_ai_helper.llm import LLMError, OpenAIChatClient

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


def _build_llm_client(preset: ModelPreset) -> OpenAIChatClient:
    return OpenAIChatClient(
        base_url=preset.base_url,
        api_key=preset.api_key,
        model=preset.model,
        supports_vision=preset.supports_vision,
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


@router.post("/style")
async def create_style(body: StyleRequest, request: Request) -> dict[str, Any]:
    name = body.name or f"ai-assistant/style-{int(time.time())}"

    modules, translate_skipped = styles_module.translate_recommendation(body.recommendation)
    result = styles_module.build_style(name, modules)

    skipped_ops = [
        {"module": s["op"], "control": None, "reason": s["reason"]}
        for s in result["skipped_ops"]
    ] + translate_skipped

    style_dir: Path | None = getattr(request.app.state, "style_dir", None)
    path = styles_module.write_style_file(result["xml"], name, style_dir)

    return {
        "file": str(path),
        "included_ops": result["included_ops"],
        "skipped_ops": skipped_ops,
        "manual_steps": [_manual_step(s) for s in skipped_ops],
    }
