"""Phase 6 integrations — offline tests (mock providers, no external creds)."""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.services.messaging import (
    get_sms_provider, get_whatsapp_provider,
    MockSMSProvider, MockWhatsAppProvider, AfricaTalkingProvider, WhatsAppCloudProvider,
)


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****4100"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****4100")
        await c.post("/auth/verify-code", json={"phone": "+254****4100", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****4100", "pin": "1234",
            "business_name": "Integ Test", "business_type": "retail",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.fixture(autouse=True)
def _restore_settings():
    saved = (
        settings.SMS_PROVIDER, settings.AFRICASTALKING_API_KEY,
        settings.AFRICASTALKING_USERNAME, settings.WHATSAPP_API_TOKEN,
        settings.WHATSAPP_PHONE_NUMBER_ID,
    )
    yield
    (
        settings.SMS_PROVIDER, settings.AFRICASTALKING_API_KEY,
        settings.AFRICASTALKING_USERNAME, settings.WHATSAPP_API_TOKEN,
        settings.WHATSAPP_PHONE_NUMBER_ID,
    ) = saved


def test_sms_provider_mock_when_no_creds():
    settings.SMS_PROVIDER = "mock"
    setattr(settings, "AFRICASTALKING_API_KEY", None)
    p = get_sms_provider()
    assert isinstance(p, MockSMSProvider)


def test_sms_provider_at_when_configured():
    settings.SMS_PROVIDER = "africastalking"
    setattr(settings, "AFRICASTALKING_API_KEY", "k")
    setattr(settings, "AFRICASTALKING_USERNAME", "u")
    p = get_sms_provider()
    assert isinstance(p, AfricaTalkingProvider)


@pytest.mark.asyncio
async def test_mock_sms_send():
    p = MockSMSProvider()
    r = await p.send("+254****5678", "hi")
    assert r.ok and r.provider == "mock" and len(p.sent) == 1


@pytest.mark.asyncio
async def test_mock_whatsapp_send():
    p = MockWhatsAppProvider()
    r = await p.send("+254****5678", "hi", template="hello")
    assert r.ok and r.provider == "mock"


def test_whatsapp_provider_mock_when_no_creds():
    setattr(settings, "WHATSAPP_API_TOKEN", None)
    setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    p = get_whatsapp_provider()
    assert isinstance(p, MockWhatsAppProvider)


def test_whatsapp_provider_cloud_when_configured():
    setattr(settings, "WHATSAPP_API_TOKEN", "t")
    setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "pid")
    p = get_whatsapp_provider()
    assert isinstance(p, WhatsAppCloudProvider)


@pytest.mark.asyncio
async def test_integrations_sms_send_endpoint_mock(auth_client):
    r = await auth_client.post("/integrations/sms/send", json={"to": "+254****5678", "message": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["mock"] is True


@pytest.mark.asyncio
async def test_integrations_whatsapp_send_endpoint_mock(auth_client):
    r = await auth_client.post("/integrations/whatsapp/send", json={"to": "+254****5678", "message": "hi"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_integrations_status(auth_client):
    r = await auth_client.get("/integrations/status")
    assert r.status_code == 200
    assert "sms_provider" in r.json()


@pytest.mark.asyncio
async def test_integrations_sms_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/integrations/sms/send", json={"to": "x", "message": "y"})
    assert r.status_code in (401, 403)
