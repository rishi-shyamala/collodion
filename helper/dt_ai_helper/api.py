"""HTTP route handlers implementing the helper API contract (plan §5.2).

Everything here reads shared state off ``request.app.state`` (set up by
``main.create_app``) rather than via constructor injection, so later workers
can add routes to this same router with a small diff instead of threading
new parameters through a factory function.

Seam for other workers
-----------------------
``/chat`` enqueues a job of kind ``"chat"`` whose handler is
``run_chat_job`` below. Today that handler is a canned echo. Worker W5 (LLM
chat) is expected to replace the *body* of ``run_chat_job`` with a call into
``llm.py`` / ``prompts.py`` / RAG retrieval — the route, request/response
models, and job plumbing should not need to change. Likewise `/optimize`,
`/vision`, and `/style` (owned by other workers) can be added to this same
``router`` following the `/chat` pattern: validate a pydantic body, call
``request.app.state.job_manager.submit(<kind>, payload)``, return
``{"job_id": job_id}``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dt_ai_helper import __version__
from dt_ai_helper import styles as styles_module

router = APIRouter()


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
# /chat + /jobs/{id}
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    history_id: str | None = None
    image_context: dict[str, Any] | None = Field(default=None)


async def run_chat_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Job handler for kind ``"chat"``.

    Placeholder pipeline: echoes the user's message back. Worker W5 replaces
    this body with real LLM + RAG + prompt assembly; the payload shape
    (``message``, ``history_id``, ``image_context``) and return shape
    (``{"answer": str, "style": {...} | None}``) are the contract other
    pieces (Lua transcript rendering) are built against, per plan §5.2/§5.3.
    """
    message = payload.get("message", "")
    return {"answer": f"Echo: {message}", "style": None}


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
