"""Phase 8: business-logic edge-case coverage hardening.

Tests the core business modules (payments, sales, inventory, customers, auth)
against edge cases that the application is *already* expected to handle:
  - payments: negative / zero amounts rejected
  - payments: duplicate M-Pesa callback does not create a duplicate payment
  - sales:    duplicate void action on an already-voided sale is rejected
  - inventory: low-stock threshold firing (quantity <= min_quantity)
  - inventory: duplicate barcode creation is rejected
  - customers: credit over-payment (exceeds balance) rejected
  - auth:     invalid phone / pin validation
  - auth:     business creation defaults (currency, timezone, active, branch)

NOTE: These tests assert *current* application behavior only. No application
logic was modified to make them pass. See the Phase 8 report for an observed
gap (the sales module has no submission-level idempotency key to prevent
duplicate sale creation from a double-submit).
"""
import itertools
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.core.database import get_session_factory
from app.models import Business, Branch, User


_phone_counter = itertools.count()


def _unique_phone() -> str:
    """A valid-format Kenyan phone that is unique per test process run."""
    n = next(_phone_counter)
    return f"+254712{n:06d}"


async def _register(client: AsyncClient, phone: str, pin: str = "1234",
                    business_name: str = "Phase8 Biz",
                    business_type: str = "shop") -> dict:
    await client.post("/auth/send-code", json={"phone": phone})
    from app.api.auth.routes import _sms_codes
    code = _sms_codes.get(phone)
    if code:
        await client.post("/auth/verify-code", json={"phone": phone, "code": code})
    reg = await client.post("/auth/register", json={
        "phone": phone, "pin": pin,
        "business_name": business_name, "business_type": business_type,
    })
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    return reg.json()


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await _register(c, _unique_phone())
        yield c


@pytest.fixture
async def authed_session():
    """A DB session bound to the test database (mirrors the app's engine)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


# --------------------------------------------------------------------------
# PAYMENTS
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stk_push_zero_amount_rejected(auth_client):
    """Amount of 0 must be rejected (our guard: amount < 1)."""
    resp = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254712345600", "amount": 0, "reference": "Zero Test",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_stk_push_negative_amount_rejected(auth_client):
    """Negative amounts must be rejected."""
    resp = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254712345600", "amount": -50, "reference": "Neg Test",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_mpesa_callback_no_duplicate_payment(auth_client):
    """Replaying an M-Pesa callback must not create a second payment record."""
    push = await auth_client.post("/payments/mpesa/stk-push", json={
        "phone": "+254712345600", "amount": 500, "reference": "Dup Callback",
    })
    assert push.status_code == 200
    checkout_id = push.json()["checkout_request_id"]

    callback = {
        "Body": {"stkCallback": {
            "MerchantRequestID": push.json()["merchant_request_id"],
            "CheckoutRequestID": checkout_id,
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {"Item": [
                {"Name": "Amount", "Value": 500},
                {"Name": "MpesaReceiptNumber", "Value": "MOCKDUP01"},
                {"Name": "TransactionDate", "Value": "20260710120000"},
                {"Name": "PhoneNumber", "Value": "254700000000"},
            ]},
        }}
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        first = await c.post("/payments/mpesa/callback", json=callback)
        assert first.status_code == 200
        # Replay the exact same callback
        second = await c.post("/payments/mpesa/callback", json=callback)
        assert second.status_code == 200

    history = await auth_client.get("/payments/history")
    # The callback stamps the payment with the M-Pesa receipt number; replaying
    # the callback must update the same record rather than create a new one.
    items = [p for p in history.json()["items"]
             if p["reference"] == "MOCKDUP01"]
    assert len(items) == 1, "callback replay must not duplicate the payment"
    assert items[0]["status"] == "completed"


# --------------------------------------------------------------------------
# SALES
# --------------------------------------------------------------------------

@pytest.fixture
async def sample_product(auth_client):
    r = await auth_client.post("/products", json={
        "name": "Phase8 Chips", "price": 35000, "category": "Food",
        "unit": "pcs", "quantity": 50, "barcode": "9000000000001",
    })
    return r.json()


@pytest.mark.asyncio
async def test_void_already_voided_sale_rejected(auth_client, sample_product):
    """Voiding an already-voided sale must be rejected (duplicate action guard)."""
    create = await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 1}],
        "payment_method": "cash",
    })
    sid = create.json()["id"]
    first = await auth_client.post(f"/sales/{sid}/void")
    assert first.status_code == 200
    second = await auth_client.post(f"/sales/{sid}/void")
    assert second.status_code == 400


@pytest.mark.asyncio
async def test_create_sale_empty_items_rejected(auth_client):
    """A sale with no line items must be rejected by schema validation."""
    resp = await auth_client.post("/sales", json={
        "items": [], "payment_method": "mpesa",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_zero_quantity_rejected(auth_client, sample_product):
    """A sale line item with quantity < 1 must be rejected by schema validation."""
    resp = await auth_client.post("/sales", json={
        "items": [{"product_id": sample_product["id"], "quantity": 0}],
        "payment_method": "mpesa",
    })
    assert resp.status_code == 422


# --------------------------------------------------------------------------
# INVENTORY
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_stock_threshold_fires(auth_client):
    """A product at/below its min_quantity must appear in low-stock."""
    low = await auth_client.post("/products", json={
        "name": "Low Stock Item", "price": 1000, "category": "Food",
        "quantity": 3, "min_quantity": 5, "barcode": "9000000000002",
    })
    assert low.status_code == 201
    resp = await auth_client.get("/products/low-stock")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert low.json()["id"] in ids


@pytest.mark.asyncio
async def test_low_stock_threshold_boundary_equal(auth_client):
    """quantity == min_quantity is the boundary and must fire (<=)."""
    boundary = await auth_client.post("/products", json={
        "name": "Boundary Stock", "price": 1000, "category": "Food",
        "quantity": 5, "min_quantity": 5, "barcode": "9000000000003",
    })
    resp = await auth_client.get("/products/low-stock")
    ids = [p["id"] for p in resp.json()]
    assert boundary.json()["id"] in ids


@pytest.mark.asyncio
async def test_low_stock_not_firing_when_healthy(auth_client):
    """A well-stocked product must not appear in low-stock."""
    healthy = await auth_client.post("/products", json={
        "name": "Healthy Stock", "price": 1000, "category": "Food",
        "quantity": 100, "min_quantity": 5, "barcode": "9000000000004",
    })
    resp = await auth_client.get("/products/low-stock")
    ids = [p["id"] for p in resp.json()]
    assert healthy.json()["id"] not in ids


@pytest.mark.asyncio
async def test_duplicate_barcode_rejected(auth_client):
    """Creating a product with a duplicate barcode must be rejected."""
    first = await auth_client.post("/products", json={
        "name": "Dup A", "price": 1000, "category": "Food",
        "barcode": "9000000000005",
    })
    assert first.status_code == 201
    second = await auth_client.post("/products", json={
        "name": "Dup B", "price": 2000, "category": "Food",
        "barcode": "9000000000005",
    })
    assert second.status_code == 409


# --------------------------------------------------------------------------
# CUSTOMERS
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_credit_overpay_rejected(auth_client):
    """Paying more credit than the outstanding balance must be rejected."""
    create = await auth_client.post("/customers", json={
        "name": "Overpay Customer", "phone": "+254712345601",
        "credit_limit": 100000,
    })
    cid = create.json()["id"]
    add = await auth_client.post(f"/customers/{cid}/credit/add?amount=50000")
    assert add.status_code == 200
    overpay = await auth_client.post(f"/customers/{cid}/credit/pay?amount=60000")
    assert overpay.status_code == 400


@pytest.mark.asyncio
async def test_customer_credit_zero_rejected(auth_client):
    """A zero credit addition must be rejected (amount >= 1)."""
    create = await auth_client.post("/customers", json={
        "name": "Zero Credit", "phone": "+254712345602",
    })
    cid = create.json()["id"]
    resp = await auth_client.post(f"/customers/{cid}/credit/add?amount=0")
    assert resp.status_code == 422


# --------------------------------------------------------------------------
# AUTH
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_code_invalid_phone_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/auth/send-code", json={"phone": "not-a-phone"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_pin_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/auth/register", json={
            "phone": _unique_phone(), "pin": "12",
            "business_name": "Bad Pin", "business_type": "shop",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_invalid_pin_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        phone = _unique_phone()
        await _register(c, phone, pin="1234")
        bad = await c.post("/auth/login", json={"phone": phone, "pin": "0000"})
        assert bad.status_code == 401


@pytest.mark.asyncio
async def test_business_creation_defaults(auth_client, authed_session):
    """A newly registered business must get sane defaults + a default branch."""
    me = await auth_client.get("/auth/me")
    assert me.status_code == 200
    user_phone = me.json()["phone"]

    biz = (await authed_session.execute(
        select(Business).where(Business.phone == user_phone)
    )).scalar_one_or_none()
    assert biz is not None
    assert biz.currency == "KES"
    assert biz.timezone == "Africa/Nairobi"
    assert biz.is_active is True

    branch = (await authed_session.execute(
        select(Branch).where(Branch.business_id == biz.id)
    )).scalars().all()
    assert len(branch) >= 1
    assert branch[0].name == "Main Branch"

    owner = (await authed_session.execute(
        select(User).where(User.business_id == biz.id, User.role == "owner")
    )).scalar_one_or_none()
    assert owner is not None
    assert owner.name == "Owner"
