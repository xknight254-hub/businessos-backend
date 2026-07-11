import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/auth/send-code", json={"phone": "+254****7777"})
        from app.api.auth.routes import _sms_codes
        code = _sms_codes.get("+254****7777")
        await c.post("/auth/verify-code", json={"phone": "+254****7777", "code": code})
        reg = await c.post("/auth/register", json={
            "phone": "+254****7777", "pin": "1234",
            "business_name": "Payment Test", "business_type": "shop",
        })
        token = reg.json()["access_token"]
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


@pytest.mark.asyncio
async def test_stk_push_mock(auth_client):
    """STK Push in mock mode should return success."""
    response = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****",
        "amount": 100,
        "reference": "Test Payment",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["response_code"] == "0"
    assert data["is_mock"] is True


@pytest.mark.asyncio
async def test_stk_push_invalid_amount(auth_client):
    response = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****",
        "amount": -1,
        "reference": "Test",
    })
    assert response.status_code == 400  # Our validation, not Pydantic's


@pytest.mark.asyncio
async def test_mpesa_callback_success(auth_client):
    """Simulate M-Pesa callback for a successful payment."""
    # First initiate payment to get checkout ID
    push = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****",
        "amount": 500,
        "reference": "Callback Test",
    })
    checkout_id = push.json()["checkout_request_id"]
    
    # Simulate callback
    callback_payload = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": push.json()["merchant_request_id"],
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 500},
                        {"Name": "MpesaReceiptNumber", "Value": "MOCK123ABC"},
                        {"Name": "TransactionDate", "Value": "20260710120000"},
                        {"Name": "PhoneNumber", "Value": "254700000000"},
                    ]
                },
            }
        }
    }
    # No auth needed for callback
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post("/payments/mpesa/callback", json=callback_payload)
        assert response.status_code == 200
        assert response.json()["ResultCode"] == 0


@pytest.mark.asyncio
async def test_mpesa_callback_preserves_reference_and_queryable(auth_client):
    """Regression: callback must NOT overwrite `reference` (checkout ID) with
    the M-Pesa receipt, otherwise /mpesa/query/{checkout_id} can't find it."""
    from app.core.database import get_session_factory
    from app.modules.accounting.models import Payment
    from sqlalchemy import select

    push = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****", "amount": 500, "reference": "RefPreserve",
    })
    checkout_id = push.json()["checkout_request_id"]
    callback_payload = {
        "Body": {"stkCallback": {
            "MerchantRequestID": push.json()["merchant_request_id"],
            "CheckoutRequestID": checkout_id,
            "ResultCode": 0,
            "ResultDesc": "ok",
            "CallbackMetadata": {"Item": [
                {"Name": "Amount", "Value": 500},
                {"Name": "MpesaReceiptNumber", "Value": "MOCK123ABC"},
            ]},
        }}
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/payments/mpesa/callback", json=callback_payload)

    # reference must remain the checkout ID; mpesa_receipt must hold the receipt
    factory = get_session_factory()
    async with factory() as db:
        from sqlalchemy import select
        pay = (await db.execute(select(Payment).where(Payment.reference == checkout_id))).scalar_one_or_none()
        assert pay is not None, "payment should remain findable by checkout ID"
        assert pay.mpesa_receipt == "MOCK123ABC"

    # and the query endpoint must locate it post-callback (ResultCode 0 = completed)
    q = await auth_client.post(f"/payments/mpesa/query/{checkout_id}")
    assert q.status_code == 200
    assert q.json().get("ResultCode") == "0"


@pytest.mark.asyncio
async def test_query_payment_status(auth_client):
    push = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****",
        "amount": 200,
        "reference": "Query Test",
    })
    checkout_id = push.json()["checkout_request_id"]
    response = await auth_client.post(f"/payments/mpesa/query/{checkout_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_payment_history(auth_client):
    await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254****",
        "amount": 300,
        "reference": "History Test",
    })
    response = await auth_client.get("/payments/history")
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1
