"""Tests for M2.3 rate limiting and M2.4 JWT refresh rotation."""
import asyncio
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token, decode_token, hash_pin
from app.core.database import get_session_factory
from app.models import User, Business
from app.main import app


def _make_owner(role="owner", uid="u-rl", bid="b-rl"):
    async def _run():
        f = get_session_factory()
        async with f() as s:
            biz = Business(id=bid, name="B", type="shop", phone="+254****0001")
            s.add(biz)
            s.add(User(id=uid, business_id=bid, name="T", phone=biz.phone,
                       pin_hash=hash_pin("1234"), role=role, is_active=True))
            await s.commit()
    asyncio.get_event_loop().run_until_complete(_run())


def test_rate_limit_auth_returns_429():
    client = TestClient(app)
    # /api/auth/send-code is limited to 20/min. Exceed it.
    last = None
    for i in range(25):
        last = client.post("/auth/send-code", json={"phone": f"+2547{i:08d}"})
    assert last.status_code == 429
    assert last.json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in last.headers


def test_refresh_rotation_revokes_old_token():
    _make_owner()
    client = TestClient(app)
    # Issue a refresh token directly (simulating a prior login)
    old_refresh = create_refresh_token({"sub": "u-rl"})
    old_jti = decode_token(old_refresh).get("jti")
    # First refresh: should succeed and revoke old_jti
    r1 = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]
    assert decode_token(new_refresh).get("jti") != old_jti
    # Replay the OLD refresh token -> must be rejected (revoked)
    r2 = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401
    assert r2.json()["error"]["code"] == "unauthorized"


def test_refresh_rejects_access_token_as_refresh():
    _make_owner()
    client = TestClient(app)
    access = create_access_token({"sub": "u-rl", "business_id": "b-rl", "role": "owner"})
    r = client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
