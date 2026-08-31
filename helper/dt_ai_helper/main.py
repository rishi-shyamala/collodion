"""App factory, auth middleware, and process lifecycle for dt-ai-helper.

Plan §3 / §5.2 / Phase 0:

- Bind ``127.0.0.1`` only, OS-assigned port (bind port 0).
- Generate a random bearer token at startup; every request must carry
  ``Authorization: Bearer <token>`` or get a 401.
- Write ``{port, token, pid}`` as JSON to a mode-600 runtime file so the Lua
  front-end can discover us.
- Detect/kill a stale previous instance via the pid recorded in that file
  before binding a new one (plan Risks: "Helper orphaned or port conflict").
- Self-terminate ~10 minutes after the last ``/heartbeat`` (or since start,
  if none has arrived yet), so the helper never outlives darktable.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import socket
import stat
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from dt_ai_helper.api import ConfigStore, router, run_chat_job
from dt_ai_helper.jobs import JobManager

DEFAULT_HEARTBEAT_TIMEOUT = 600.0  # 10 minutes, per plan §3/§5.2
WATCHDOG_INTERVAL = 5.0


def default_runtime_dir() -> Path:
    """Best-effort per-platform cache directory, no extra dependency.

    Linux: $XDG_CACHE_HOME or ~/.cache
    macOS: ~/Library/Caches
    Windows: %LOCALAPPDATA% or ~/AppData/Local
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "dt-ai-helper"


def default_runtime_file() -> Path:
    return default_runtime_dir() / "runtime.json"


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform.startswith("win"):
            # os.kill(pid, 0) is not supported on Windows for arbitrary
            # signals; use CTRL_BREAK_EVENT-free existence check instead.
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                return True
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but is owned by someone else -- treat as alive.
        return True
    except OSError:
        return False


def kill_stale_instance(runtime_file: Path) -> None:
    """If a runtime file from a previous run exists and its pid is alive, kill it."""
    if not runtime_file.exists():
        return
    try:
        data = json.loads(runtime_file.read_text())
        pid = int(data.get("pid", -1))
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return
    if pid and pid != os.getpid() and _pid_is_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            # Give it a brief moment to exit.
            for _ in range(20):
                if not _pid_is_alive(pid):
                    break
                time.sleep(0.1)
        except OSError:
            pass


def write_runtime_file(runtime_file: Path, *, port: int, token: str) -> None:
    runtime_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"port": port, "token": token, "pid": os.getpid()}
    # Write then chmod (rather than relying on umask) so the token is never
    # briefly world-readable.
    runtime_file.write_text(json.dumps(payload))
    try:
        os.chmod(runtime_file, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # best-effort on platforms without POSIX permission bits


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects any request lacking ``Authorization: Bearer <token>``.

    Every endpoint requires auth -- there is no public/unauthenticated route,
    including /health, per the task spec.
    """

    def __init__(self, app: Any, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        header = request.headers.get("authorization", "")
        expected = f"Bearer {self._token}"
        if not secrets.compare_digest(header, expected):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


def create_app(
    token: str,
    *,
    heartbeat_timeout: float = DEFAULT_HEARTBEAT_TIMEOUT,
) -> FastAPI:
    """Build the FastAPI app. Pure/offline-friendly: no sockets, no files.

    Used directly by tests (with a known token) and by ``cli()`` (with a
    randomly generated one).
    """
    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.job_manager.start()
        try:
            yield
        finally:
            await app.state.job_manager.stop()

    app = FastAPI(title="dt-ai-helper", lifespan=_lifespan)
    app.state.config_store = ConfigStore()
    app.state.job_manager = JobManager()
    app.state.job_manager.register_handler("chat", run_chat_job)
    app.state.heartbeat_timeout = heartbeat_timeout
    app.state.last_heartbeat = time.time()
    app.state.token = token

    app.add_middleware(BearerAuthMiddleware, token=token)
    app.include_router(router)

    return app


async def _watchdog(app: FastAPI, server: uvicorn.Server) -> None:
    """Self-terminate ~heartbeat_timeout seconds after the last /heartbeat."""
    timeout = app.state.heartbeat_timeout
    while not server.should_exit:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        idle_for = time.time() - app.state.last_heartbeat
        if idle_for > timeout:
            server.should_exit = True
            break


async def _serve(
    app: FastAPI,
    sock: socket.socket,
    runtime_file: Path,
    token: str,
) -> None:
    port = sock.getsockname()[1]
    write_runtime_file(runtime_file, port=port, token=token)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    watchdog_task = asyncio.create_task(_watchdog(app, server))
    try:
        await server.serve(sockets=[sock])
    finally:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        try:
            runtime_file.unlink(missing_ok=True)
        except OSError:
            pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dt-ai-helper")
    parser.add_argument(
        "--runtime-file",
        type=Path,
        default=default_runtime_file(),
        help="Path to write {port, token, pid} JSON (mode 600).",
    )
    parser.add_argument(
        "--heartbeat-timeout",
        type=float,
        default=DEFAULT_HEARTBEAT_TIMEOUT,
        help="Seconds of no /heartbeat before self-exit.",
    )
    return parser.parse_args(argv)


def cli(argv: list[str] | None = None) -> None:
    """Entrypoint installed as the ``dt-ai-helper`` console script."""
    args = parse_args(argv)
    runtime_file: Path = args.runtime_file

    kill_stale_instance(runtime_file)

    token = secrets.token_urlsafe(32)
    app = create_app(token, heartbeat_timeout=args.heartbeat_timeout)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(100)

    try:
        asyncio.run(_serve(app, sock, runtime_file, token))
    finally:
        sock.close()


if __name__ == "__main__":
    cli()
