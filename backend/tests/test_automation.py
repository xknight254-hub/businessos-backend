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
            "business_name": "Auto Test", "business_type": "restaurant",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}

        # Create some products and sales for rule evaluation
        p = (await c.post("/products", json={
            "name": "Auto Product", "price": 10000, "category": "Food",
            "unit": "pcs", "quantity": 50,
        })).json()

        # Create customers with credit
        cust = (await c.post("/customers", json={
            "name": "Debtor", "phone": "+254****7001", "credit_limit": 500000,
        })).json()
        await c.post(f"/customers/{cust['id']}/credit/add?amount=50000")

        # Sales
        for i in range(5):
            await c.post("/sales", json={
                "items": [{"product_id": p["id"], "quantity": 2}],
                "payment_method": "cash",
            })

        yield c


@pytest.mark.asyncio
async def test_seed_templates(auth_client):
    response = await auth_client.post("/automation/templates")
    assert response.status_code == 200
    data = response.json()
    assert data["seeded"] > 0


@pytest.mark.asyncio
async def test_list_rules(auth_client):
    await auth_client.post("/automation/templates")
    response = await auth_client.get("/automation/rules")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_create_rule(auth_client):
    response = await auth_client.post("/automation/rules", json={
        "name": "Custom Alert",
        "trigger_type": "low_stock",
        "condition_config": {"max_days_until_out": 2},
        "action_type": "send_notification",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Custom Alert"


@pytest.mark.asyncio
async def test_run_automation(auth_client):
    await auth_client.post("/automation/templates")
    response = await auth_client.post("/automation/run")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


@pytest.mark.asyncio
async def test_automation_logs(auth_client):
    response = await auth_client.get("/automation/logs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_suggestions(auth_client):
    response = await auth_client.get("/automation/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_update_delete_rule(auth_client):
    create = await auth_client.post("/automation/rules", json={
        "name": "Temp Rule", "trigger_type": "anomaly", "action_type": "send_notification",
    })
    rid = create.json()["id"]

    update = await auth_client.patch(f"/automation/rules/{rid}", json={"name": "Updated Rule"})
    assert update.status_code == 200

    delete = await auth_client.delete(f"/automation/rules/{rid}")
    assert delete.status_code == 204
