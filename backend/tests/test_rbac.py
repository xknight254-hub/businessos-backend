"""Tests for M2.1 RBAC: fine-grained permission enforcement."""
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.core.rbac import require_permission, role_can, PERMISSIONS
from app.core.security import create_access_token, hash_pin
from app.core.database import get_session_factory
from app.models import User, Business
from app.main import app


def _make_user(role: str, user_id: str, business_id: str):
    async def _run():
        factory = get_session_factory()
        async with factory() as s:
            biz = Business(id=business_id, name="B", type="shop", phone=f"+25470000{user_id[-3:]}")
            s.add(biz)
            u = User(
                id=user_id, business_id=business_id, name="T", phone=biz.phone,
                pin_hash=hash_pin("1234"), role=role, is_active=True,
            )
            s.add(u)
            await s.commit()
    asyncio.get_event_loop().run_until_complete(_run())


def _token(role: str, user_id: str = "u-1", business_id: str = "b-1") -> str:
    return create_access_token({"sub": user_id, "business_id": business_id, "role": role})


def test_role_can_helper():
    assert role_can("owner", "product:delete") is True
    assert role_can("manager", "product:delete") is False
    assert role_can("staff", "customer:credit") is False
    assert role_can("manager", "customer:credit") is True


def test_unknown_permission_denied_by_default():
    assert "nonexistent:perm" not in PERMISSIONS


def test_staff_cannot_delete_product():
    _make_user("staff", "u-staff", "b-staff")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token('staff', 'u-staff', 'b-staff')}"}
    r = client.delete("/products/anything", headers=headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_owner_reaches_delete_handler():
    _make_user("owner", "u-owner", "b-owner")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_token('owner', 'u-owner', 'b-owner')}"}
    r = client.delete("/products/nonexistent-id", headers=headers)
    # Owner passes RBAC; route then 404s on missing product (not 403).
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def _auth(role: str, uid: str, bid: str) -> dict:
    return {"Authorization": f"Bearer {_token(role, uid, bid)}"}


def test_staff_cannot_add_customer_credit():
    _make_user("staff", "u-cred-staff", "b-cred-staff")
    client = TestClient(app)
    r = client.post("/customers/cid/credit/add?amount=100",
                    headers=_auth("staff", "u-cred-staff", "b-cred-staff"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_manager_can_add_customer_credit_reaches_handler():
    _make_user("manager", "u-cred-mgr", "b-cred-mgr")
    client = TestClient(app)
    # Manager passes RBAC; missing customer -> 404 (not 403).
    r = client.post("/customers/nope/credit/add?amount=100",
                    headers=_auth("manager", "u-cred-mgr", "b-cred-mgr"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_staff_cannot_void_sale():
    _make_user("staff", "u-void-staff", "b-void-staff")
    client = TestClient(app)
    r = client.post("/sales/sid/void", headers=_auth("staff", "u-void-staff", "b-void-staff"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_owner_can_void_sale_reaches_handler():
    _make_user("owner", "u-void-owner", "b-void-owner")
    client = TestClient(app)
    # Owner passes RBAC; missing sale -> 404 (not 403).
    r = client.post("/sales/nope/void", headers=_auth("owner", "u-void-owner", "b-void-owner"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_staff_can_create_sale_reaches_handler():
    _make_user("staff", "u-sale-staff", "b-sale-staff")
    client = TestClient(app)
    # Staff allowed by sale:create; empty body -> 422 validation (not 403).
    r = client.post("/sales", json={}, headers=_auth("staff", "u-sale-staff", "b-sale-staff"))
    assert r.status_code != 403
