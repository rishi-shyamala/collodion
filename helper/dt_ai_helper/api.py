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
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from dt_ai_helper import __version__

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
