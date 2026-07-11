"""LLM calling service (Phase 5 — AI Platform).

Thin wrapper over the Omniroute gateway so domain code calls
`await llm.chat(...)` / `await llm.structured(...)` without knowing
the vendor. All failures raise GatewayError; callers decide UX.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.gateway import (
    ChatMessage, GatewayError, OmnirouteGateway, gateway,
)


async def chat(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: Optional[int] = None,
) -> str:
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))
    result = await gateway.chat(
        messages, model=model, temperature=temperature, max_tokens=max_tokens,
    )
    return result.content


async def structured(
    prompt: str,
    *,
    system: Optional[str] = None,
    model: str = "gpt-4o-mini",
    **extra: Any,
) -> dict:
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))
    return await gateway.chat_json(messages, model=model, **extra)
