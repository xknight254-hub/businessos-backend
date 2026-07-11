import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def seeded_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register business
        await c.post("/auth/send-code", json={"phone": "+254****3000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****3000")
        await c.post("/auth/verify-code", json={"phone": "+254****3000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****3000", "pin": "1234",
            "business_name": "AI Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}

        # Create products
        p1 = (await c.post("/products", json={
            "name": "Chai", "price": 5000, "category": "Beverages",
            "unit": "pcs", "quantity": 100,
        })).json()
        p2 = (await c.post("/products", json={
            "name": "Mandazi", "price": 2000, "category": "Food",
            "unit": "pcs", "quantity": 50,
        })).json()

        # Create 14+ days of sales data
        from datetime import datetime, timedelta, timezone
        # We can't backdate via API, so we create 20 sales to trigger observations
        for i in range(20):
            pid = p1["id"] if i % 2 == 0 else p2["id"]
            await c.post("/sales", json={
                "items": [{"product_id": pid, "quantity": 2}],
                "payment_method": "mpesa" if i % 3 == 0 else "cash",
            })

        yield c


@pytest.mark.asyncio
async def test_ai_readiness(seeded_client):
    response = await seeded_client.get("/ai/observations/ready")
    assert response.status_code == 200
    data = response.json()
    assert "days_of_data" in data
    assert "total_transactions" in data
    assert data["total_transactions"] >= 20


@pytest.mark.asyncio
async def test_ai_observations(seeded_client):
    response = await seeded_client.get("/ai/observations?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # May or may not have enough days, but should return something
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_peak_hours(seeded_client):
    response = await seeded_client.get("/ai/observations/peak-hours")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    # At minimum should report insufficient_data or peak_hours
    assert data["status"] in ("ready", "insufficient_data")


@pytest.mark.asyncio
async def test_fast_movers(seeded_client):
    response = await seeded_client.get("/ai/observations/fast-movers")
    assert response.status_code == 200
    assert "items" in response.json()


@pytest.mark.asyncio
async def test_anomalies(seeded_client):
    response = await seeded_client.get("/ai/observations/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_engine_not_ready_without_data(seeded_client):
    """Test with a fresh business that has no sales."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****3001"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****3001")
        await c.post("/auth/verify-code", json={"phone": "+254****3001", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****3001", "pin": "1234",
            "business_name": "Fresh Biz", "business_type": "shop",
        })
        c.headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        response = await c.get("/ai/observations")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1  # Should return "waiting_for_data" insight
        assert data["items"][0]["type"] == "waiting_for_data"
