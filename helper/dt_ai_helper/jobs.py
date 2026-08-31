"""In-process async job queue.

Plan §5.3: one asyncio worker task processes jobs sequentially; results are
returned whole (no streaming to the Lua client). The last ``MAX_JOBS`` jobs
are retained for polling via ``GET /jobs/{id}``.

Job "kinds" are registered by name -> async callable so later workers (chat,
optimize, vision) can plug in their own pipelines without touching this
module. See ``dt_ai_helper.pipelines`` for the registry and the echo stub
used until the real LLM pipeline (W5) lands.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

JobStatus = Literal["queued", "running", "done", "error"]

#: Number of most-recent jobs kept in memory for polling.
MAX_JOBS = 20

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class Job:
    id: str
    kind: str
    payload: dict[str, Any]
    status: JobStatus = "queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_public_dict(self) -> dict[str, Any]:
        """Shape returned by GET /jobs/{id} (plan §5.2)."""
        out: dict[str, Any] = {"id": self.id, "status": self.status}
        if self.status == "done" and self.result is not None:
            out.update(self.result)
        if self.status == "error" and self.error is not None:
            out["error"] = self.error
        return out


class JobManager:
    """Single-worker asyncio job queue.

    Jobs are dispatched to handlers registered under a ``kind`` string (e.g.
    ``"chat"``). This lets other workers add new job kinds (optimize, vision,
    style) without editing this file: they call ``register_handler`` from
    their own module at import time.
    """

    def __init__(self, max_jobs: int = MAX_JOBS) -> None:
        self._max_jobs = max_jobs
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handlers: dict[str, JobHandler] = {}
        self._worker_task: asyncio.Task[None] | None = None

    def register_handler(self, kind: str, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

    def submit(self, kind: str, payload: dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        job = Job(id=job_id, kind=kind, payload=payload)
        self._jobs[job_id] = job
        self._evict_old()
        self._queue.put_nowait(job_id)
        return job_id

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def _evict_old(self) -> None:
        while len(self._jobs) > self._max_jobs:
            self._jobs.popitem(last=False)

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self._queue.get()
            job = self._jobs.get(job_id)
            if job is None:
                continue
            job.status = "running"
            job.updated_at = time.time()
            handler = self._handlers.get(job.kind)
            try:
                if handler is None:
                    raise ValueError(f"no handler registered for job kind {job.kind!r}")
                job.result = await handler(job.payload)
                job.status = "done"
            except Exception as exc:  # noqa: BLE001 - surfaced to client as error
                job.error = str(exc)
                job.status = "error"
            finally:
                job.updated_at = time.time()
