"""Offline FastAPI TestClient tests for the helper skeleton (plan §5.2).

No network access; everything runs against an in-process app built by
``dt_ai_helper.main.create_app`` with a known token.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from dt_ai_helper.main import create_app

TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client():
    app = create_app(TOKEN)
    with TestClient(app) as c:
        yield c


def test_missing_auth_is_rejected(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 401


def test_wrong_token_is_rejected(client: TestClient):
    resp = client.get("/health", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_health(client: TestClient):
    resp = client.get("/health", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["model_ready"] is False


def test_config_roundtrip_and_redaction(client: TestClient):
    # No presets yet.
    resp = client.get("/config", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"active": None, "presets": {}}

    preset = {
        "name": "local-ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "super-secret",
        "model": "qwen3",
        "supports_vision": False,
    }
    resp = client.post("/config", json=preset, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] == "local-ollama"
    assert body["presets"]["local-ollama"]["api_key"] == "***"
    assert "super-secret" not in resp.text

    resp = client.get("/config", headers=AUTH)
    body = resp.json()
    assert body["presets"]["local-ollama"]["model"] == "qwen3"
    assert body["presets"]["local-ollama"]["api_key"] == "***"

    # model_ready flips true once an active preset with base_url+model exists.
    resp = client.get("/health", headers=AUTH)
    assert resp.json()["model_ready"] is True


def test_config_requires_auth(client: TestClient):
    resp = client.post("/config", json={"name": "x", "base_url": "y", "model": "z"})
    assert resp.status_code == 401


def test_chat_poll_done_echo_roundtrip(client: TestClient):
    resp = client.post("/chat", json={"message": "hello there"}, headers=AUTH)
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert job_id

    deadline = time.time() + 5
    body = None
    while time.time() < deadline:
        poll = client.get(f"/jobs/{job_id}", headers=AUTH)
        assert poll.status_code == 200
        body = poll.json()
        if body["status"] in ("done", "error"):
            break
        time.sleep(0.05)

    assert body is not None
    assert body["status"] == "done"
    assert body["answer"] == "Echo: hello there"


def test_job_not_found(client: TestClient):
    resp = client.get("/jobs/does-not-exist", headers=AUTH)
    assert resp.status_code == 404


def test_heartbeat_updates_deadline(client: TestClient):
    app = client.app
    before = app.state.last_heartbeat
    time.sleep(0.05)
    resp = client.post("/heartbeat", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert app.state.last_heartbeat > before


def test_heartbeat_requires_auth(client: TestClient):
    resp = client.post("/heartbeat")
    assert resp.status_code == 401
