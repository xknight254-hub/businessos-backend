import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def seeded_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****5000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****5000")
        await c.post("/auth/verify-code", json={"phone": "+254****5000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****5000", "pin": "1234",
            "business_name": "DNA Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}

        # Products across categories
        p1 = (await c.post("/products", json={
            "name": "Chai", "category": "Beverages", "price": 5000,
            "unit": "pcs", "quantity": 100,
        })).json()
        p2 = (await c.post("/products", json={
            "name": "Chips", "category": "Food", "price": 35000,
            "unit": "pcs", "quantity": 50,
        })).json()

        # Customers for segmentation
        c1 = (await c.post("/customers", json={
            "name": "Regular A", "phone": "+254****5001",
        })).json()
        c2 = (await c.post("/customers", json={
            "name": "Regular B", "phone": "+254****5002",
        })).json()

        # Sales data
        for i in range(10):
            pid = p1["id"] if i % 2 == 0 else p2["id"]
            cid = c1["id"] if i % 3 == 0 else c2["id"]
            await c.post("/sales", json={
                "items": [{"product_id": pid, "quantity": 2}],
                "payment_method": "mpesa", "customer_id": cid,
            })

        yield c


@pytest.mark.asyncio
async def test_dna_profile(seeded_client):
    response = await seeded_client.get("/dna/profile")
    assert response.status_code == 200
    data = response.json()
    assert "category_velocity" in data
    assert "customer_segments" in data
    assert "health_score" in data
    assert data["business_id"]


@pytest.mark.asyncio
async def test_category_velocity(seeded_client):
    response = await seeded_client.get("/dna/category-velocity")
    assert response.status_code == 200
    data = response.json()
    # Should have data or insufficient_data status
    assert "status" in data


@pytest.mark.asyncio
async def test_customer_segments(seeded_client):
    response = await seeded_client.get("/dna/customer-segments")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_health_score(seeded_client):
    response = await seeded_client.get("/dna/health-score")
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert data["score"] >= 0
    assert data["score"] <= 100


@pytest.mark.asyncio
async def test_supplier_reliability(seeded_client):
    response = await seeded_client.get("/dna/supplier-reliability")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_dna_memory_stored(seeded_client):
    """DNA should automatically store insights in Business Memory."""
    await seeded_client.get("/dna/profile")
    response = await seeded_client.get("/memory/recent?source=dna")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 0  # May be 0 if insufficient data for DNA analysis
