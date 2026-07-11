import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register a business and get token
        await c.post("/auth/send-code", json={"phone": "+254****6000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****6000")
        await c.post("/auth/verify-code", json={"phone": "+254****6000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****6000", "pin": "1234",
            "business_name": "Inventory Test", "business_type": "shop",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.mark.asyncio
async def test_create_product(auth_client):
    response = await auth_client.post("/products", json={
        "name": "Cooking Oil 5L",
        "name_sw": "Mafuta ya Kupikia 5L",
        "barcode": "8991234567890",
        "category": "Food",
        "unit": "pcs",
        "price": 65000,  # KES 650 in cents
        "cost_price": 52000,
        "quantity": 10,
        "min_quantity": 2,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Cooking Oil 5L"
    assert data["price"] == 65000
    assert data["barcode"] == "8991234567890"


@pytest.mark.asyncio
async def test_list_products(auth_client):
    # Create a product first
    await auth_client.post("/products", json={
        "name": "Sugar 2kg", "barcode": "8901234567890",
        "category": "Food", "unit": "pcs",
        "price": 30000, "quantity": 20,
    })
    # List
    response = await auth_client.get("/products?page=1&per_page=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_barcode_lookup(auth_client):
    await auth_client.post("/products", json={
        "name": "Rice 1kg", "barcode": "7777777777777",
        "category": "Food", "unit": "pcs", "price": 25000,
    })
    response = await auth_client.get("/products/search/barcode?barcode=7777777777777")
    assert response.status_code == 200
    assert response.json()["found"] is True


@pytest.mark.asyncio
async def test_barcode_not_found(auth_client):
    response = await auth_client.get("/products/search/barcode?barcode=0000000000000")
    assert response.status_code == 200
    assert response.json()["found"] is False


@pytest.mark.asyncio
async def test_update_product(auth_client):
    create = await auth_client.post("/products", json={
        "name": "Salt 500g", "barcode": "8888888888888",
        "category": "Food", "unit": "pcs", "price": 5000,
    })
    pid = create.json()["id"]
    response = await auth_client.patch(f"/products/{pid}", json={"price": 6000})
    assert response.status_code == 200
    assert response.json()["price"] == 6000


@pytest.mark.asyncio
async def test_delete_product(auth_client):
    create = await auth_client.post("/products", json={
        "name": "Tea Leaves", "barcode": "6666666666666",
        "category": "Beverages", "unit": "pcs", "price": 8000,
    })
    pid = create.json()["id"]
    response = await auth_client.delete(f"/products/{pid}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_stock_adjustment(auth_client):
    create = await auth_client.post("/products", json={
        "name": "Flour 2kg", "barcode": "5555555555555",
        "category": "Food", "unit": "pcs", "price": 15000, "quantity": 10,
    })
    pid = create.json()["id"]
    # Remove 3 units
    response = await auth_client.post("/products/stock/adjust", json={
        "product_id": pid, "quantity": -3, "reason": "sold",
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_categories_list(auth_client):
    await auth_client.post("/products", json={
        "name": "Bread", "category": "Food", "unit": "pcs", "price": 5000,
    })
    await auth_client.post("/products", json={
        "name": "Soap", "category": "Cleaning", "unit": "pcs", "price": 3000,
    })
    response = await auth_client.get("/products/categories/list")
    assert response.status_code == 200
    cats = response.json()["categories"]
    assert len(cats) >= 2
