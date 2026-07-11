import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****6000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****6000")
        await c.post("/auth/verify-code", json={"phone": "+254****6000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****6000", "pin": "1234",
            "business_name": "Partner Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.mark.asyncio
async def test_chat_greeting(auth_client):
    response = await auth_client.post("/partner/chat", json={
        "message": "hello",
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "conversation_id" in data
    assert len(data["reply"]) > 0


@pytest.mark.asyncio
async def test_chat_health_score(auth_client):
    response = await auth_client.post("/partner/chat", json={
        "message": "What is my business health score?",
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert data["tool_used"] is not None


@pytest.mark.asyncio
async def test_chat_help(auth_client):
    response = await auth_client.post("/partner/chat", json={
        "message": "help",
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data["reply"]) > 0
    assert len(data["suggestions"]) > 0


@pytest.mark.asyncio
async def test_chat_conversation_persistence(auth_client):
    # First message
    r1 = await auth_client.post("/partner/chat", json={
        "message": "hello",
    })
    cid = r1.json()["conversation_id"]

    # Second message with same conversation_id
    r2 = await auth_client.post("/partner/chat", json={
        "message": "how is my business?",
        "conversation_id": cid,
    })
    assert r2.status_code == 200
    assert r2.json()["conversation_id"] == cid


@pytest.mark.asyncio
async def test_chat_low_stock(auth_client):
    response = await auth_client.post("/partner/chat", json={
        "message": "Do I have any low stock?",
    })
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data


@pytest.mark.asyncio
async def test_chat_customers(auth_client):
    response = await auth_client.post("/partner/chat", json={
        "message": "Who owes me money?",
    })
    assert response.status_code == 200
    assert "reply" in response.json()


@pytest.mark.asyncio
async def test_capabilities(auth_client):
    response = await auth_client.get("/partner/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "capabilities" in data
    assert len(data["capabilities"]) >= 5
    assert "languages" in data
