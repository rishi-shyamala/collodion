"""Offline tests for the LLM chat pipeline (plan §5.4/§5.5, W5 scope).

Everything here runs against mock HTTP transports (``httpx.MockTransport``)
or an in-process ``TestClient`` -- no real network calls, per
``documentation/agent-insights/002-conventions-for-subagents.md`` ("Offline
testing").
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from dt_ai_helper import api as api_module
from dt_ai_helper.llm import (
    LLMError,
    OpenAIChatClient,
    VisionNotAllowed,
    build_vision_content,
    extract_json,
    guard_vision_upload,
    is_local_host,
)
from dt_ai_helper.main import create_app
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


# ---------------------------------------------------------------------------
# OpenAIChatClient: request shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_shape():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return _ok_response("hello back")

    client = OpenAIChatClient(
        base_url="http://127.0.0.1:11434/v1",
        api_key="secret-key",
        model="qwen3",
        transport=httpx.MockTransport(handler),
    )
    try:
        answer = await client.chat(
            [{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=128,
        )
    finally:
        await client.aclose()

    assert answer == "hello back"
    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    body = json.loads(request.content)
    assert body["model"] == "qwen3"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert body["temperature"] == 0.5
    assert body["max_tokens"] == 128
    assert "response_format" not in body


# ---------------------------------------------------------------------------
# OpenAIChatClient: retry on 429 then success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, text="rate limited")
        return _ok_response("second try worked")

    client = OpenAIChatClient(
        base_url="http://localhost:8080",
        api_key=None,
        model="local-model",
        backoff_base=0.001,  # keep the test fast
        transport=httpx.MockTransport(handler),
    )
    try:
        answer = await client.chat([{"role": "user", "content": "retry me"}])
    finally:
        await client.aclose()

    assert answer == "second try worked"
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_exhausts_retries_and_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    client = OpenAIChatClient(
        base_url="http://localhost:8080",
        api_key=None,
        model="local-model",
        max_retries=2,
        backoff_base=0.001,
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(LLMError):
            await client.chat([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# strict_json mode: response_format success, and fenced-JSON fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_json_uses_response_format_when_supported():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return _ok_response('{"assessment": "ok", "recommendations": []}')

    client = OpenAIChatClient(
        base_url="http://localhost:8080",
        api_key=None,
        model="local-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.chat_json([{"role": "user", "content": "analyze"}])
    finally:
        await client.aclose()

    assert result == {"assessment": "ok", "recommendations": []}


@pytest.mark.asyncio
async def test_chat_json_falls_back_to_fenced_extraction():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        if "response_format" in body:
            # Simulate an endpoint that rejects the parameter outright.
            return httpx.Response(400, text="unknown parameter: response_format")
        text = (
            "Sure, here's the analysis:\n\n"
            "```json\n"
            '{"assessment": "flat midtones", "recommendations": []}\n'
            "```\n"
        )
        return _ok_response(text)

    client = OpenAIChatClient(
        base_url="http://localhost:8080",
        api_key=None,
        model="local-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.chat_json([{"role": "user", "content": "analyze"}])
    finally:
        await client.aclose()

    assert calls["n"] == 2
    assert result == {"assessment": "flat midtones", "recommendations": []}


def test_extract_json_handles_bare_and_fenced_and_prose():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('here you go: {"a": 3} -- hope that helps') == {"a": 3}
    with pytest.raises(LLMError):
        extract_json("no json anywhere in this string")


# ---------------------------------------------------------------------------
# Vision privacy guard
# ---------------------------------------------------------------------------


def test_is_local_host():
    assert is_local_host("http://127.0.0.1:11434/v1")
    assert is_local_host("http://localhost:8080")
    assert not is_local_host("https://api.openai.com/v1")


def test_guard_refuses_cloud_without_consent():
    with pytest.raises(VisionNotAllowed):
        guard_vision_upload(base_url="https://api.openai.com/v1", allow_upload=False)


def test_guard_allows_cloud_with_consent():
    guard_vision_upload(base_url="https://api.openai.com/v1", allow_upload=True)  # no raise


def test_guard_allows_localhost_without_consent():
    guard_vision_upload(base_url="http://127.0.0.1:11434/v1", allow_upload=False)  # no raise


def test_build_vision_content_refuses_cloud_without_consent():
    with pytest.raises(VisionNotAllowed):
        build_vision_content(
            "what do you see?",
            b"not-really-a-jpeg",
            base_url="https://openrouter.ai/api/v1",
            allow_upload=False,
        )


def test_build_vision_content_attaches_image_when_allowed():
    content = build_vision_content(
        "what do you see?",
        b"not-really-a-jpeg",
        base_url="http://127.0.0.1:11434/v1",
        allow_upload=False,
    )
    assert content[0] == {"type": "text", "text": "what do you see?"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# ---------------------------------------------------------------------------
# End-to-end: POST /chat -> job -> real pipeline against a mock LLM server
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    app = create_app(TOKEN)
    with TestClient(app) as c:
        yield c


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


def test_chat_without_preset_returns_helpful_error(client: TestClient):
    resp = client.post("/chat", json={"message": "hi"}, headers=AUTH)
    job_id = resp.json()["job_id"]
    body = _poll_job(client, job_id)
    assert body["status"] == "error"
    assert "preset" in body["error"].lower()


def test_chat_end_to_end_with_edit_state_and_rag(client: TestClient, monkeypatch):
    """POST /chat with a message + image_context (fixture sidecar) should
    call the LLM with MODULE LIBRARY excerpts and the decoded edit state in
    the outgoing request, and return the mocked reply as the answer."""
    captured_requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(json.loads(request.content))
        return _ok_response("Use filmic rgb's white relative exposure to tame the highlights.")

    transport = httpx.MockTransport(handler)

    def fake_build_client(preset):
        return OpenAIChatClient(
            base_url=preset.base_url,
            api_key=preset.api_key,
            model=preset.model,
            supports_vision=preset.supports_vision,
            transport=transport,
        )

    monkeypatch.setattr(api_module, "_build_llm_client", fake_build_client)

    resp = client.post(
        "/config",
        json={
            "name": "local",
            "base_url": "http://127.0.0.1:11434/v1",
            "model": "qwen3",
            "supports_vision": False,
        },
        headers=AUTH,
    )
    assert resp.status_code == 200

    sidecar = FIXTURES / "generated_tier1.xmp"
    assert sidecar.is_file()

    resp = client.post(
        "/chat",
        json={
            "message": "the sky is blown out, how do I recover the highlights?",
            "history_id": "img-1",
            "image_context": {
                "filepath": "/photos/img.RAF",
                "sidecar": str(sidecar),
                "exif": {"iso": 200, "aperture": 8.0},
            },
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    body = _poll_job(client, job_id)
    assert body["status"] == "done"
    assert body["answer"] == "Use filmic rgb's white relative exposure to tame the highlights."
    assert body["style"] is None

    assert len(captured_requests) == 1
    messages = captured_requests[0]["messages"]
    assert messages[0]["role"] == "system"
    user_content = messages[-1]["content"]
    assert "MODULE LIBRARY" in user_content
    assert "filmicrgb" in user_content  # RAG hit for "blown out" highlights
    assert "CURRENT EDIT STATE" in user_content
    assert "history source: xmp" in user_content
    # A Tier-1 decoded value from tests/fixtures/generated_tier1.yaml.
    assert "filmicrgb" in user_content and "contrast=1.2" in user_content

    # A second turn on the same history_id should carry the first exchange
    # forward as prior messages, not just the freshest context blocks.
    resp = client.post(
        "/chat",
        json={"message": "what about noise?", "history_id": "img-1"},
        headers=AUTH,
    )
    job_id = resp.json()["job_id"]
    body = _poll_job(client, job_id)
    assert body["status"] == "done"

    second_request_messages = captured_requests[1]["messages"]
    roles = [m["role"] for m in second_request_messages]
    assert roles.count("user") == 2
    assert roles.count("assistant") == 1


def test_history_clear_endpoint(client: TestClient, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return _ok_response("ack")

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        api_module,
        "_build_llm_client",
        lambda preset: OpenAIChatClient(
            base_url=preset.base_url,
            api_key=preset.api_key,
            model=preset.model,
            transport=transport,
        ),
    )
    client.post(
        "/config",
        json={"name": "local", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen3"},
        headers=AUTH,
    )
    resp = client.post("/chat", json={"message": "hi", "history_id": "img-2"}, headers=AUTH)
    _poll_job(client, resp.json()["job_id"])

    history_store = client.app.state.chat_histories
    assert history_store.get("img-2")  # populated after the turn above

    resp = client.post("/history/clear", json={"history_id": "img-2"}, headers=AUTH)
    assert resp.status_code == 200
    assert history_store.get("img-2") == []


def test_history_clear_requires_auth(client: TestClient):
    resp = client.post("/history/clear", json={"history_id": "x"})
    assert resp.status_code == 401
