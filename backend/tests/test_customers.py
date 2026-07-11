import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****8000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****8000")
        await c.post("/auth/verify-code", json={"phone": "+254****8000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****8000", "pin": "1234",
            "business_name": "Reporting Test", "business_type": "shop",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.mark.asyncio
async def test_create_customer(auth_client):
    response = await auth_client.post("/customers", json={
        "name": "Jane Doe",
        "phone": "+254****9999",
        "credit_limit": 500000,  # KES 5,000
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["credit_limit"] == 500000


@pytest.mark.asyncio
async def test_list_customers(auth_client):
    await auth_client.post("/customers", json={"name": "Customer A", "phone": "+254****1111"})
    await auth_client.post("/customers", json={"name": "Customer B", "phone": "+254****2222"})
    response = await auth_client.get("/customers")
    assert response.status_code == 200
    assert response.json()["total"] >= 2


@pytest.mark.asyncio
async def test_customer_credit_flow(auth_client):
    create = await auth_client.post("/customers", json={
        "name": "Credit Customer",
        "phone": "+254****3333",
        "credit_limit": 100000,  # KES 1,000
    })
    cid = create.json()["id"]
    
    # Add credit
    add = await auth_client.post(f"/customers/{cid}/credit/add?amount=50000")
    assert add.status_code == 200
    assert add.json()["credit_balance"] == 50000
    
    # Pay credit
    pay = await auth_client.post(f"/customers/{cid}/credit/pay?amount=20000")
    assert pay.status_code == 200
    assert pay.json()["credit_balance"] == 30000


@pytest.mark.asyncio
async def test_customer_search(auth_client):
    await auth_client.post("/customers", json={"name": "Unique Name", "phone": "+254****4444"})
    response = await auth_client.get("/customers?search=Unique")
    assert response.status_code == 200
    assert response.json()["total"] >= 1
