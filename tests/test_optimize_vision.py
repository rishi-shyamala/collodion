"""Offline tests for POST /optimize and POST /vision (plan §5.2/§5.5,
Phases 3-4, W6 scope).

Everything runs against an in-process ``TestClient`` with the LLM's
``httpx`` transport swapped for a ``MockTransport`` (via monkeypatching
``api_module._build_llm_client``), per
``documentation/agent-insights/002-conventions-for-subagents.md``'s
offline-testing rule. Preview images are tiny synthetic JPEGs built with
Pillow, not fixture files.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import numpy as np
import pytest
from dt_ai_helper import api as api_module
from dt_ai_helper.llm import OpenAIChatClient
from dt_ai_helper.main import create_app
from fastapi.testclient import TestClient
from PIL import Image

TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(TOKEN)
    app.state.style_dir = tmp_path / "styles"
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def preview_path(tmp_path: Path) -> str:
    """A deliberately underexposed, low-contrast preview JPEG."""
    arr = np.full((32, 32, 3), 40, dtype=np.uint8)
    path = tmp_path / "preview.jpg"
    Image.fromarray(arr, mode="RGB").save(path, format="JPEG", quality=90)
    return str(path)


def _poll_job(client: TestClient, job_id: str) -> dict:
    deadline = time.time() + 5
    body: dict | None = None
    while time.time() < deadline:
        poll = client.get(f"/jobs/{job_id}", headers=AUTH)
        assert poll.status_code == 200
        body = poll.json()
        if body["status"] in ("done", "error"):
            break
        time.sleep(0.02)
    assert body is not None
    return body


def _configure_preset(client: TestClient, **overrides) -> None:
    preset = {
        "name": "local",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen3",
        "supports_vision": False,
    }
    preset.update(overrides)
    resp = client.post("/config", json=preset, headers=AUTH)
    assert resp.status_code == 200


def _patch_llm_client(monkeypatch, transport: httpx.MockTransport, *, allow_upload=False) -> None:
    def fake_build_client(preset, *, allow_upload=allow_upload):
        return OpenAIChatClient(
            base_url=preset.base_url,
            api_key=preset.api_key,
            model=preset.model,
            supports_vision=preset.supports_vision,
            allow_upload=allow_upload,
            transport=transport,
        )

    monkeypatch.setattr(api_module, "_build_llm_client", fake_build_client)


# ---------------------------------------------------------------------------
# /optimize
# ---------------------------------------------------------------------------


def test_optimize_without_preset_returns_helpful_error(client: TestClient, preview_path: str):
    resp = client.post("/optimize", json={"preview_path": preview_path}, headers=AUTH)
    job_id = resp.json()["job_id"]
    body = _poll_job(client, job_id)
    assert body["status"] == "error"
    assert "preset" in body["error"].lower()


def test_optimize_missing_preview_returns_clear_error(client: TestClient, monkeypatch):
    _configure_preset(client)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("LLM should never be called when the preview is missing")

    _patch_llm_client(monkeypatch, httpx.MockTransport(handler))

    resp = client.post(
        "/optimize", json={"preview_path": "/nonexistent/preview.jpg"}, headers=AUTH
    )
    body = _poll_job(client, resp.json()["job_id"])
    assert body["status"] == "error"
    assert "preview" in body["error"].lower()


def test_optimize_end_to_end_parses_json_and_builds_style(
    client: TestClient, preview_path: str, monkeypatch
):
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        content = json.dumps(
            {
                "assessment": "Underexposed with flat midtones.",
                "recommendations": [
                    {
                        "module": "exposure",
                        "why": "Raise overall brightness.",
                        "settings": [{"control": "exposure", "value": "+1.2 EV"}],
                        "priority": 1,
                    },
                    {
                        "module": "denoiseprofile",
                        "why": "Not encodable without a base state.",
                        "settings": [{"control": "strength", "value": "1.0"}],
                        "priority": 2,
                    },
                ],
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    _patch_llm_client(monkeypatch, httpx.MockTransport(handler))
    _configure_preset(client)

    resp = client.post(
        "/optimize",
        json={
            "preview_path": preview_path,
            "image_context": {"exif": {"iso": 400}},
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = _poll_job(client, resp.json()["job_id"])

    assert body["status"] == "done"
    assert "recommendation" in body
    assert body["recommendation"]["assessment"] == "Underexposed with flat midtones."
    assert len(body["recommendation"]["recommendations"]) == 2

    # Rendered transcript text mentions the recommended module.
    assert "exposure" in body["answer"]

    # A style was built for the encodable subset (exposure); denoiseprofile
    # has no static default params (see styles.py's DEFAULT_PARAMS note) so
    # it should surface as a manual step, not crash the whole style build.
    assert body["style"] is not None
    style_path = Path(body["style"]["file"])
    assert style_path.exists()
    assert "exposure" in body["style"]["summary"]

    # The outgoing LLM request should have used strict-JSON mode and named
    # a tag-derived retrieval query result (MODULE LIBRARY block present).
    assert len(captured) == 1
    request_body = captured[0]
    assert request_body["response_format"] == {"type": "json_object"}
    user_content = request_body["messages"][-1]["content"]
    assert "ISSUE TAGS" in user_content
    assert "MODULE LIBRARY" in user_content
    assert "HISTOGRAM STATISTICS" in user_content


def test_optimize_no_recommendations_means_no_style(
    client: TestClient, preview_path: str, monkeypatch
):
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"assessment": "Looks fine.", "recommendations": []})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    _patch_llm_client(monkeypatch, httpx.MockTransport(handler))
    _configure_preset(client)

    resp = client.post("/optimize", json={"preview_path": preview_path}, headers=AUTH)
    body = _poll_job(client, resp.json()["job_id"])

    assert body["status"] == "done"
    assert body["style"] is None
    assert body["recommendation"]["recommendations"] == []


# ---------------------------------------------------------------------------
# /vision
# ---------------------------------------------------------------------------


def test_vision_without_preset_returns_helpful_error(client: TestClient, preview_path: str):
    resp = client.post("/vision", json={"preview_path": preview_path}, headers=AUTH)
    body = _poll_job(client, resp.json()["job_id"])
    assert body["status"] == "error"
    assert "preset" in body["error"].lower()


def test_vision_unsupported_preset_returns_clear_error(client: TestClient, preview_path: str):
    _configure_preset(client, supports_vision=False)

    resp = client.post("/vision", json={"preview_path": preview_path}, headers=AUTH)
    body = _poll_job(client, resp.json()["job_id"])

    assert body["status"] == "error"
    assert "vision" in body["error"].lower()


def test_vision_cloud_without_consent_returns_clear_error(client: TestClient, preview_path: str):
    _configure_preset(
        client,
        base_url="https://api.openai.com/v1",
        supports_vision=True,
    )

    resp = client.post(
        "/vision",
        json={"preview_path": preview_path, "allow_upload": False},
        headers=AUTH,
    )
    body = _poll_job(client, resp.json()["job_id"])

    assert body["status"] == "error"
    assert "refus" in body["error"].lower()
    assert "consent" in body["error"].lower() or "allow_upload" in body["error"].lower()


def test_vision_two_pass_makes_two_llm_calls(
    client: TestClient, preview_path: str, monkeypatch
):
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            # Pass 1 (describe): should carry the image as a vision content part.
            content = body["messages"][-1]["content"]
            assert isinstance(content, list)
            assert any(part.get("type") == "image_url" for part in content)
            reply = "Backlit portrait with a blown-out sky and warm cast."
        else:
            # Pass 2 (recommend): text-only, references pass 1's description.
            content = body["messages"][-1]["content"]
            assert isinstance(content, str)
            assert "IMAGE DESCRIPTION" in content
            assert "blown-out sky" in content
            reply = "Use filmic rgb's white relative exposure to tame the sky."
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}]})

    _patch_llm_client(monkeypatch, httpx.MockTransport(handler))
    _configure_preset(client, base_url="http://127.0.0.1:11434/v1", supports_vision=True)

    resp = client.post(
        "/vision",
        json={"message": "what's wrong with this shot?", "preview_path": preview_path},
        headers=AUTH,
    )
    body = _poll_job(client, resp.json()["job_id"])

    assert body["status"] == "done"
    assert len(calls) == 2
    assert body["answer"] == "Use filmic rgb's white relative exposure to tame the sky."
    assert body["description"] == "Backlit portrait with a blown-out sky and warm cast."
    assert body["style"] is None


def test_vision_missing_preview_returns_clear_error(client: TestClient, monkeypatch):
    _configure_preset(client, supports_vision=True)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("LLM should never be called when the preview is missing")

    _patch_llm_client(monkeypatch, httpx.MockTransport(handler))

    resp = client.post(
        "/vision", json={"preview_path": "/nonexistent/preview.jpg"}, headers=AUTH
    )
    body = _poll_job(client, resp.json()["job_id"])
    assert body["status"] == "error"
    assert "preview" in body["error"].lower()


def test_vision_requires_auth(client: TestClient, preview_path: str):
    resp = client.post("/vision", json={"preview_path": preview_path})
    assert resp.status_code == 401


def test_optimize_requires_auth(client: TestClient, preview_path: str):
    resp = client.post("/optimize", json={"preview_path": preview_path})
    assert resp.status_code == 401
