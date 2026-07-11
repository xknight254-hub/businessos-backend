"""Tests for Phase 2 security baseline: M2.5 headers + M2.2 audit logging."""
from fastapi.testclient import TestClient

from app.core.audit import write_audit
from app.core.database import get_session_factory
from app.models import AuditLog
from app.main import app


def test_security_headers_present_on_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    h = r.headers
    assert h.get("x-content-type-options") == "nosniff"
    assert h.get("x-frame-options") == "DENY"
    assert "default-src 'none'" in h.get("content-security-policy", "")
    assert h.get("referrer-policy") == "no-referrer"


def test_audit_write_inserts_row():
    async def _run():
        await write_audit(
            business_id="biz-001",
            user_id="user-001",
            action="create",
            resource="product",
            resource_id="p-1",
            details="test audit",
            ip_address="127.0.0.1",
        )
        factory = get_session_factory()
        async with factory() as s:
            from sqlalchemy import select, func
            n = (await s.execute(select(func.count()).select_from(AuditLog))).scalar()
            return n

    import asyncio
    count = asyncio.get_event_loop().run_until_complete(_run())
    assert count >= 1
