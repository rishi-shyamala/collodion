"""OpenAI-compatible chat client (plan §5.4).

A single class speaking ``POST {base_url}/chat/completions`` -- the swap
point for the whole assistant: changing models means changing
``{base_url, model, api_key}``, nothing else. Configuration comes from
whichever :class:`dt_ai_helper.api.ConfigStore` preset is active; this
module deliberately does not import ``api.py`` to avoid a cycle (``api.py``
imports this module to build a client from the active preset), so the
constructor just takes the preset fields directly as keyword arguments.

Supports:

- ``temperature`` / ``max_tokens`` passthrough.
- Bounded retry-with-backoff on 429/5xx responses and transport errors.
- ``chat_json`` ("strict_json" mode): tries ``response_format:
  {"type": "json_object"}`` first, and falls back to fenced/brace JSON
  extraction from a plain-text response for endpoints that reject the
  ``response_format`` parameter.
- Vision content parts (``image_url`` with a base64 data URL), gated by
  :func:`guard_vision_upload` -- plan §5.4's hard rule: *never* attach an
  image unless the request is a vision request AND (the endpoint is
  localhost OR the user has opted in via ``allow_upload``).
- An injectable ``httpx`` transport, so tests never touch the network (see
  ``tests/test_llm.py``).
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5  # seconds; doubled each retry attempt

#: Response codes worth retrying: rate limiting and server-side failures.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

#: Hostnames treated as "local" for the vision privacy guard.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    """The LLM endpoint could not be reached, or returned something unusable."""


class VisionNotAllowed(LLMError):
    """A vision request would leak image bytes without consent (plan §5.4/§11)."""


def is_local_host(base_url: str) -> bool:
    """True if ``base_url``'s host is loopback."""
    host = urlparse(base_url).hostname or ""
    return host.lower() in LOCAL_HOSTS


def guard_vision_upload(*, base_url: str, allow_upload: bool) -> None:
    """Raise :class:`VisionNotAllowed` unless it is safe to send an image.

    Safe means: the endpoint is localhost, OR the caller has explicitly set
    the "allow image upload to cloud endpoints" preference. Call this
    *before* building any vision content part -- the point is to never
    construct the payload in the first place, not to strip it after.
    """
    if is_local_host(base_url) or allow_upload:
        return
    raise VisionNotAllowed(
        "refusing to send an image to a non-local endpoint "
        f"({urlparse(base_url).hostname!r}) without allow_upload consent"
    )


def image_content_part(image_bytes: bytes, *, mime_type: str = "image/jpeg") -> dict[str, Any]:
    """Build an OpenAI-style ``image_url`` content part from raw image bytes."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}


def build_vision_content(
    text: str,
    image_bytes: bytes,
    *,
    base_url: str,
    allow_upload: bool,
    mime_type: str = "image/jpeg",
) -> list[dict[str, Any]]:
    """Build a vision user-message ``content`` list, enforcing the privacy guard.

    Raises :class:`VisionNotAllowed` instead of ever returning a payload
    that would leak an image. This is the single choke point Phase 4
    (vision, owned by W6) should route through rather than re-implementing
    the localhost-or-consent check.
    """
    guard_vision_upload(base_url=base_url, allow_upload=allow_upload)
    return [
        {"type": "text", "text": text},
        image_content_part(image_bytes, mime_type=mime_type),
    ]


def extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a chat completion's text content.

    Tries, in order: the whole string as JSON; a ```json fenced block; the
    first balanced ``{...}`` substring. Raises :class:`LLMError` if none of
    those parse -- used as the ``strict_json`` fallback when an endpoint
    doesn't honour ``response_format``.
    """
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = _FENCE_RE.search(stripped)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = stripped.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            char = stripped[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

    raise LLMError(f"could not extract JSON from LLM response: {stripped[:300]!r}")


class OpenAIChatClient:
    """Speaks the OpenAI Chat Completions API against any compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        supports_vision: bool = False,
        allow_upload: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.supports_vision = supports_vision
        self.allow_upload = allow_upload
        self.max_retries = max(1, max_retries)
        self.backoff_base = backoff_base

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OpenAIChatClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def guard_vision(self) -> None:
        """Raise unless this client is allowed to carry image content."""
        guard_vision_upload(base_url=self.base_url, allow_upload=self.allow_upload)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        is_vision_request: bool = False,
    ) -> str:
        """Send a chat completion request, returning the reply text.

        Retries on 429/5xx and transport errors, bounded by ``max_retries``.
        """
        if is_vision_request:
            self.guard_vision()

        body: dict[str, Any] = {"model": self.model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if response_format is not None:
            body["response_format"] = response_format

        return await self._request(body)

    async def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """``strict_json`` mode (plan §5.4): structured output for Optimize.

        Tries ``response_format: json_object`` first; if the endpoint
        rejects that parameter or returns text that isn't valid JSON, falls
        back to a plain request plus :func:`extract_json`.
        """
        try:
            content = await self.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(content)
        except (LLMError, json.JSONDecodeError):
            pass

        content = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return extract_json(content)

    async def _request(self, body: dict[str, Any]) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.post("/chat/completions", json=body)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    await self._backoff(attempt)
                    continue
                raise LLMError(f"connection to LLM endpoint failed: {exc}") from exc

            if resp.status_code in RETRYABLE_STATUS:
                last_error = LLMError(f"{resp.status_code}: {resp.text[:300]}")
                if attempt < self.max_retries - 1:
                    await self._backoff(attempt)
                    continue
                raise last_error

            if resp.status_code >= 400:
                raise LLMError(f"LLM endpoint returned {resp.status_code}: {resp.text[:500]}")

            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMError(f"unexpected response shape from LLM endpoint: {data!r}") from exc

        raise LLMError(f"LLM request failed after {self.max_retries} attempts: {last_error}")

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(self.backoff_base * (2**attempt))
