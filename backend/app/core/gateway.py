"""Omniroute AI model gateway (Phase 5 — AI Platform).

Thin async client over the OpenAI-compatible /v1/chat/completions
contract — the common denominator for model gateways. Swap the
base URL / key via settings; the call shape stays the same, so the
rest of the app never imports a vendor SDK.

All methods raise `GatewayError` on non-2xx or missing config, never
leak the API key, and never block the event loop.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger

logger = get_logger("businessos.gateway")

DEFAULT_MODEL = "gpt-4o-mini"  # placeholder; set per-call
REQUEST_TIMEOUT = 60.0


class GatewayError(Exception):
    """Raised when the model gateway call fails (config or transport)."""


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResult:
    content: str
    model: str
    raw: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return (self.usage or {}).get("total_tokens", 0)


class OmnirouteGateway:
    """OpenAI-compatible chat client backed by Omniroute."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self.api_key = api_key or settings.OMNIROUTE_API_KEY
        self.base_url = (base_url or settings.OMNIROUTE_BASE_URL).rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _client_(self) -> httpx.AsyncClient:
        if not self.api_key:
            raise ConfigurationError(
                "OMNIROUTE_API_KEY is not set; AI calls unavailable."
            )
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[ChatMessage | dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
        **extra: Any,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.to_dict() if isinstance(m, ChatMessage) else m for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = response_format
        payload.update(extra)

        client = self._client_()
        try:
            resp = await client.post("/chat/completions", json=payload)
        except httpx.HTTPError as e:
            logger.error("gateway_transport_error", extra={"error": str(e)})
            raise GatewayError(f"Omniroute transport error: {e}") from e

        if resp.status_code != 200:
            logger.error(
                "gateway_http_error",
                extra={"status": resp.status_code, "body": resp.text[:500]},
            )
            raise GatewayError(
                f"Omniroute returned {resp.status_code}: {resp.text[:300]}"
            )

        return self._parse_response(resp.text, model)

    @staticmethod
    def _parse_response(text: str, model: str) -> "ChatResult":
        """Handle both SSE streams and plain JSON (OpenAI-compatible).

        Omniroute streams Server-Sent Events (`data: {...}` chunks). We
        accumulate `choices[].delta.content` and read `model`/`usage` from
        the first event that carries them. If no `data:` lines are present,
        fall back to a single JSON object.
        """
        chunks: list[str] = []
        model_out = model
        usage: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                continue
            try:
                evt = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if evt.get("model"):
                model_out = evt["model"]
            if evt.get("usage"):
                usage = evt["usage"]
            try:
                delta = evt["choices"][0]["delta"].get("content") or ""
            except (KeyError, IndexError, TypeError):
                delta = ""
            if delta:
                chunks.append(delta)
        if chunks:
            return ChatResult(
                content="".join(chunks), model=model_out, raw={}, usage=usage
            )
        # Fallback: single JSON object
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise GatewayError(f"Unexpected gateway response shape: {text[:300]}") from e
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise GatewayError(f"Unexpected gateway response shape: {data}") from e
        return ChatResult(
            content=content,
            model=data.get("model", model),
            raw=data,
            usage=data.get("usage", {}),
        )

    async def chat_json(
        self,
        messages: list[ChatMessage | dict],
        model: str = DEFAULT_MODEL,
        **extra: Any,
    ) -> dict:
        """Request JSON output (vendor `json_object` / `json` mode) and parse it."""
        result = await self.chat(
            messages,
            model=model,
            response_format={"type": "json_object"},
            **extra,
        )
        try:
            return json.loads(result.content)
        except json.JSONDecodeError as e:
            logger.error("gateway_json_parse_error", extra={"raw": result.content[:300]})
            raise GatewayError(f"Gateway did not return valid JSON: {e}") from e


# Process-wide singleton
gateway = OmnirouteGateway()
