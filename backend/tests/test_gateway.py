"""Omniroute gateway — offline contract tests (no network)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import ConfigurationError
from app.core.gateway import (
    OmnirouteGateway, GatewayError, ChatMessage,
)


def test_missing_key_raises_configuration_error(monkeypatch):
    monkeypatch.setattr("app.core.gateway.settings.OMNIROUTE_API_KEY", None)
    gw = OmnirouteGateway(api_key=None, base_url="https://x/v1")
    with pytest.raises(ConfigurationError):
        gw._client_()


def test_chat_parses_openai_shape(monkeypatch):
    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"total_tokens": 12},
    }
    fake_post = AsyncMock(return_value=fake)
    gw = OmnirouteGateway(api_key="sk-test", base_url="https://x/v1")
    monkeypatch.setattr(gw, "_client_", lambda: MagicMock(post=fake_post))

    import asyncio
    res = asyncio.get_event_loop().run_until_complete(
        gw.chat([ChatMessage(role="user", content="hi")], model="gpt-4o-mini")
    )
    assert res.content == "hello"
    assert res.model == "gpt-4o-mini"
    assert res.tokens == 12


def test_chat_non_200_raises_gateway_error(monkeypatch):
    fake = MagicMock()
    fake.status_code = 401
    fake.text = "unauthorized"
    fake_post = AsyncMock(return_value=fake)
    gw = OmnirouteGateway(api_key="sk-test", base_url="https://x/v1")
    monkeypatch.setattr(gw, "_client_", lambda: MagicMock(post=fake_post))

    import asyncio
    from app.core.gateway import GatewayError
    with pytest.raises(GatewayError):
        asyncio.get_event_loop().run_until_complete(
            gw.chat([ChatMessage(role="user", content="hi")])
        )


def test_chat_json_parses_valid_json(monkeypatch):
    fake = MagicMock()
    fake.status_code = 200
    fake.json.return_value = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }
    fake_post = AsyncMock(return_value=fake)
    gw = OmnirouteGateway(api_key="sk-test", base_url="https://x/v1")
    monkeypatch.setattr(gw, "_client_", lambda: MagicMock(post=fake_post))

    import asyncio
    out = asyncio.get_event_loop().run_until_complete(
        gw.chat_json([ChatMessage(role="user", content="hi")])
    )
    assert out == {"ok": True}
