import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def seeded_client():
    """Client with a business, products, sales, and customers for report testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register business
        await c.post("/auth/send-code", json={"phone": "+254****9000"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****9000")
        await c.post("/auth/verify-code", json={"phone": "+254****9000", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****9000", "pin": "1234",
            "business_name": "Report Test", "business_type": "shop",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}

        # Create products
        p1 = (await c.post("/products", json={
            "name": "Milk 1L", "price": 15000, "cost_price": 10000,
            "category": "Dairy", "unit": "pcs", "quantity": 50,
        })).json()
        p2 = (await c.post("/products", json={
            "name": "Bread", "price": 5000, "cost_price": 3000,
            "category": "Bakery", "unit": "pcs", "quantity": 100,
        })).json()
        p3 = (await c.post("/products", json={
            "name": "Tea", "price": 8000, "cost_price": 5000,
            "category": "Beverages", "unit": "pcs", "quantity": 30,
        })).json()

        # Create customers
        cust1 = (await c.post("/customers", json={
            "name": "Loyal Customer", "phone": "+254****1001",
            "credit_limit": 500000,
        })).json()
        await c.post(f"/customers/{cust1['id']}/credit/add?amount=50000")
        cust2 = (await c.post("/customers", json={
            "name": "Frequent Buyer", "phone": "+254****1002",
        })).json()

        # Create sales — attach to customers
        for i in range(5):
            await c.post("/sales", json={
                "items": [{"product_id": p1["id"], "quantity": 2}],
                "payment_method": "mpesa" if i % 2 == 0 else "cash",
                "customer_id": cust1["id"],
            })
        for i in range(3):
            await c.post("/sales", json={
                "items": [{"product_id": p2["id"], "quantity": 5}],
                "payment_method": "cash",
                "customer_id": cust2["id"],
            })
        await c.post("/sales", json={
            "items": [{"product_id": p3["id"], "quantity": 1}],
            "payment_method": "mpesa",
        })

        yield c


@pytest.mark.asyncio
async def test_revenue_summary(seeded_client):
    response = await seeded_client.get("/reports/revenue/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["today"] > 0
    assert data["this_month"] > 0
    assert data["trend"] in ("up", "down", "flat")


@pytest.mark.asyncio
async def test_top_products(seeded_client):
    response = await seeded_client.get("/reports/products/top?days=30&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["revenue"] > 0
    assert data[0]["product_name"]


@pytest.mark.asyncio
async def test_top_customers(seeded_client):
    response = await seeded_client.get("/reports/customers/top?days=90&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["total_spent"] > 0


@pytest.mark.asyncio
async def test_sales_chart(seeded_client):
    response = await seeded_client.get("/reports/sales/chart?days=30")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["revenue"] > 0


@pytest.mark.asyncio
async def test_profit_loss(seeded_client):
    response = await seeded_client.get("/reports/profit-loss")
    assert response.status_code == 200
    data = response.json()
    assert data["total_revenue"] > 0
    assert data["gross_profit"] > 0
    assert data["gross_margin"] > 0


@pytest.mark.asyncio
async def test_analytics_dashboard(seeded_client):
    response = await seeded_client.get("/reports/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["revenue"]["today"] > 0
    assert len(data["top_products"]) >= 1
    assert len(data["top_customers"]) >= 1
    assert len(data["sales_chart"]) >= 1
