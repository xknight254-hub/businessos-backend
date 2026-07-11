import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****4000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****4000")
        await c.post("/auth/verify-code", json={"phone": "+254****4000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****4000", "pin": "1234",
            "business_name": "Memory Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.mark.asyncio
async def test_store_memory(auth_client):
    response = await auth_client.post("/memory", json={
        "content": "Customer John prefers chips masala with extra sauce",
        "source": "observation",
        "memory_type": "semantic",
        "tags": ["customer", "preference"],
        "confidence": 0.8,
        "metadata": {"customer_id": "test123", "product": "chips masala"},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Customer John prefers chips masala with extra sauce"
    assert data["source"] == "observation"
    assert "id" in data


@pytest.mark.asyncio
async def test_search_memory(auth_client):
    # Store entries
    await auth_client.post("/memory", json={
        "content": "Peak hours are 12-2pm on weekdays",
        "source": "pattern", "memory_type": "semantic",
        "tags": ["peak_hours"], "confidence": 0.9,
    })
    await auth_client.post("/memory", json={
        "content": "Milk is a top seller — reorder every 3 days",
        "source": "pattern", "memory_type": "semantic",
        "tags": ["reorder"], "confidence": 0.85,
    })

    # Search
    response = await auth_client.post("/memory/search", json={
        "query": "peak hours",
        "limit": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any("peak" in item["content"].lower() for item in data["items"])


@pytest.mark.asyncio
async def test_memory_stats(auth_client):
    response = await auth_client.get("/memory/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_entries" in data
    assert data["total_entries"] >= 0


@pytest.mark.asyncio
async def test_recent_memories(auth_client):
    await auth_client.post("/memory", json={
        "content": "Test entry for recent list",
        "source": "conversation", "memory_type": "episodic",
        "confidence": 0.5,
    })
    response = await auth_client.get("/memory/recent?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_consolidate(auth_client):
    response = await auth_client.post("/memory/consolidate")
    assert response.status_code == 200
    data = response.json()
    assert "pruned" in data
    assert "remaining" in data
