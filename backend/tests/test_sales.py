import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****7000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****7000")
        await c.post("/auth/verify-code", json={"phone": "+254****7000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****7000", "pin": "1234",
            "business_name": "POS Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.fixture
async def sample_product(auth_client):
    r = await auth_client.post("/products", json={
        "name": "Chips Masala", "price": 35000, "category": "Food",
        "unit": "pcs", "quantity": 50, "barcode": "1111111111111",
    })
    return r.json()


@pytest.mark.asyncio
async def test_create_sale(auth_client, sample_product):
    response = await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 2}],
        "payment_method": "mpesa",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["total"] == 70000  # 35000 * 2
    assert len(data["items"]) == 1
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_create_sale_with_customer(auth_client, sample_product):
    response = await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 1}],
        "payment_method": "cash",
    })
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_list_sales(auth_client, sample_product):
    await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 1}],
        "payment_method": "mpesa",
    })
    response = await auth_client.get("/sales?page=1&per_page=10")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_daily_summary(auth_client, sample_product):
    await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 3}],
        "payment_method": "mpesa",
    })
    response = await auth_client.get("/sales/summary/daily")
    assert response.status_code == 200
    data = response.json()
    assert data["total_revenue"] >= 105000
    assert data["transaction_count"] >= 1
    assert len(data["top_products"]) >= 1


@pytest.mark.asyncio
async def test_void_sale(auth_client, sample_product):
    create = await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 1}],
        "payment_method": "cash",
    })
    sid = create.json()["id"]
    response = await auth_client.post(f"/sales/{sid}/void")
    assert response.status_code == 200
    assert response.json()["status"] == "voided"


@pytest.mark.asyncio
async def test_invalid_product_sale(auth_client):
    response = await auth_client.post("/sales", json={
        "items": [{"product_id": "nonexistent", "quantity": 1}],
        "payment_method": "mpesa",
    })
    assert response.status_code == 404
