import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_send_code(client):
    response = await client.post("/auth/send-code", json={"phone": "+254712345678"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Code sent"


@pytest.mark.asyncio
async def test_verify_code(client):
    phone = "+254712345678"
    await client.post("/auth/send-code", json={"phone": phone})
    # Code is stored in _sms_codes, retrieve it
    from app.api.auth.routes import _sms_codes
    code = _sms_codes.get(phone)
    assert code is not None
    response = await client.post("/auth/verify-code", json={"phone": phone, "code": code})
    assert response.status_code == 200
    assert response.json()["message"] == "Phone verified"


@pytest.mark.asyncio
async def test_register_and_login(client):
    phone = "+254798765432"
    await client.post("/auth/send-code", json={"phone": phone})
    from app.api.auth.routes import _sms_codes
    code = _sms_codes.get(phone)
    await client.post("/auth/verify-code", json={"phone": phone, "code": code})

    # Register
    reg_response = await client.post("/auth/register", json={
        "phone": phone,
        "pin": "1234",
        "business_name": "Test Restaurant",
        "business_type": "restaurant",
    })
    assert reg_response.status_code == 200
    reg_data = reg_response.json()
    assert "access_token" in reg_data
    assert reg_data["role"] == "owner"

    # Login
    login_response = await client.post("/auth/login", json={
        "phone": phone,
        "pin": "1234",
    })
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert "access_token" in login_data

    # Get me
    me_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["phone"] == phone

    # Invalid PIN
    bad_response = await client.post("/auth/login", json={
        "phone": phone,
        "pin": "9999",
    })
    assert bad_response.status_code == 401
