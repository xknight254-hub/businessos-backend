"""Phase 5 AI platform — offline contract + endpoint tests (no live model)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.model_router import model_router, CostTier
from app.services.document_processing import (
    UnconfiguredProcessor, get_document_processor, set_document_processor,
    DocumentProcessor, get_voice_processor, set_voice_processor, VoiceProcessor,
)


def test_model_router_resolves_tier():
    spec = model_router.resolve("insight")
    assert spec.tier in (CostTier.cheap, CostTier.balanced, CostTier.premium)
    assert model_router.resolve("chat", preferred="gpt-4o").name == "gpt-4o"


def test_ocr_unconfigured_returns_501():
    saved = get_document_processor()
    set_document_processor(UnconfiguredProcessor())
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/auth/send-code", json={"phone": "+254****4001"})
            from app.api.auth.routes import _sms_codes
            code = _sms_codes.get("+254****4001")
            await c.post("/auth/verify-code", json={"phone": "+254****4001", "code": code})
            reg = await c.post("/auth/register", json={
                "phone": "+254****4001", "pin": "1234",
                "business_name": "OCR Test", "business_type": "retail",
            })
            tok = reg.json()["access_token"]
            c.headers = {"Authorization": f"Bearer {tok}"}
            from io import BytesIO
            resp = await c.post(
                "/ai/ocr",
                files={"file": ("doc.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20), "image/png")},
            )
            return resp.status_code
    import asyncio
    code = asyncio.get_event_loop().run_until_complete(_run())
    set_document_processor(saved)
    assert code == 501


def test_ocr_configured_returns_text():
    class FakeDoc(DocumentProcessor):
        async def ocr(self, file_bytes, content_type):
            return {"text": "Ksh 850.00", "fields": {}, "confidence": 0.9}
    saved = get_document_processor()
    set_document_processor(FakeDoc())
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/auth/send-code", json={"phone": "+254****4003"})
            from app.api.auth.routes import _sms_codes
            code = _sms_codes.get("+254****4003")
            await c.post("/auth/verify-code", json={"phone": "+254****4003", "code": code})
            reg = await c.post("/auth/register", json={
                "phone": "+254****4003", "pin": "1234",
                "business_name": "OCR Test2", "business_type": "retail",
            })
            tok = reg.json()["access_token"]
            c.headers = {"Authorization": f"Bearer {tok}"}
            from io import BytesIO
            resp = await c.post(
                "/ai/ocr",
                files={"file": ("doc.png", BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20), "image/png")},
            )
            return resp.status_code, resp.json()
    import asyncio
    code, body = asyncio.get_event_loop().run_until_complete(_run())
    set_document_processor(saved)
    assert code == 200
    assert body["text"] == "Ksh 850.00" and body["confidence"] == 0.9


def test_voice_unconfigured_returns_501():
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/auth/send-code", json={"phone": "+254****4002"})
            from app.api.auth.routes import _sms_codes
            code = _sms_codes.get("+254****4002")
            await c.post("/auth/verify-code", json={"phone": "+254****4002", "code": code})
            reg = await c.post("/auth/register", json={
                "phone": "+254****4002", "pin": "1234",
                "business_name": "Voice Test", "business_type": "retail",
            })
            tok = reg.json()["access_token"]
            c.headers = {"Authorization": f"Bearer {tok}"}
            fake = b"RIFFxxxxWAVE" + b"\x00" * 20
            from io import BytesIO
            resp = await c.post(
                "/ai/voice/transcribe",
                files={"file": ("clip.wav", BytesIO(fake), "audio/wav")},
            )
            return resp.status_code
    import asyncio
    code = asyncio.get_event_loop().run_until_complete(_run())
    assert code == 501


def test_prompt_create_and_version_bump():
    async def _run():
        from app.core.database import get_session_factory
        from app.services.prompt_store import PromptStore
        factory = get_session_factory()
        async with factory() as db:
            store = PromptStore(db, "biz-prompt-test")
            p1 = await store.create(key="k1", title="v1", template="t1")
            p2 = await store.create(key="k1", title="v2", template="t2")
            active = await store.get_active("k1")
            return p1.version, p2.version, active.version, active.is_active, p1.is_active
    import asyncio
    v1, v2, av, aactive, p1active = asyncio.get_event_loop().run_until_complete(_run())
    assert (v1, v2, av) == (1, 2, 2)
    assert aactive is True and p1active is False


def test_voice_configured_returns_text():
    class FakeVoice(VoiceProcessor):
        async def transcribe(self, audio_bytes, content_type):
            return {"text": "ni mingi ya maziwa", "confidence": 0.8, "language": "sw", "entries": []}
    saved = get_voice_processor()
    set_voice_processor(FakeVoice())
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            await c.post("/auth/send-code", json={"phone": "+254****4004"})
            from app.api.auth.routes import _sms_codes
            code = _sms_codes.get("+254****4004")
            await c.post("/auth/verify-code", json={"phone": "+254****4004", "code": code})
            reg = await c.post("/auth/register", json={
                "phone": "+254****4004", "pin": "1234",
                "business_name": "Voice Test2", "business_type": "retail",
            })
            tok = reg.json()["access_token"]
            c.headers = {"Authorization": f"Bearer {tok}"}
            from io import BytesIO
            resp = await c.post(
                "/ai/voice/transcribe",
                files={"file": ("clip.wav", BytesIO(b"RIFFxxxxWAVE" + b"\x00" * 20), "audio/wav")},
            )
            return resp.status_code, resp.json()
    import asyncio
    code, body = asyncio.get_event_loop().run_until_complete(_run())
    set_voice_processor(saved)
    assert code == 200
    assert body["text"] == "ni mingi ya maziwa" and body["language"] == "sw"
