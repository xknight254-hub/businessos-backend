"""Phase 4 M4.3 — event handlers write side-effect notifications.

The conftest autouse fixture (setup_db) points app.core.database's session
factory at a fresh SQLite test.db. Handlers open their own session via the
same factory, so an event published in a test lands in the same test.db the
test can read from.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory, Base
from app.core.events import Event
from app.modules.accounting.events import PAYMENT_COMPLETED
from app.modules.inventory.events import STOCK_ADJUSTED
from app.core.handlers import on_payment_completed, on_low_stock
from app.modules.notifications.repository import NotificationRepository
from app.models import Business


async def _make_business(business_id: str):
    # Business already exists in the seeded test.db via app fixtures; we
    # create one deterministically for isolation.
    async with get_session_factory()() as s:
        b = Business(name="B", type="shop", phone="254700000001", is_active=True)
        s.add(b)
        await s.commit()
        return b.id


async def test_payment_handler_creates_notification():
    bid = await _make_business("b-pay")
    ev = Event(
        type=PAYMENT_COMPLETED, business_id=bid,
        payload={"amount": 50000, "mpesa_receipt": "ABC123"},
    )
    await on_payment_completed(ev)
    async with get_session_factory()() as s:
        repo = NotificationRepository(s, bid)
        notes = await repo.list_recent()
    assert len(notes) == 1
    assert notes[0].type == "payment_received"
    assert "KES 500" in notes[0].message


async def test_low_stock_handler_fires_below_min():
    bid = await _make_business("b-low")
    ev = Event(
        type=STOCK_ADJUSTED, business_id=bid,
        payload={"product_id": "p1", "new_quantity": 0, "min_quantity": 5},
    )
    await on_low_stock(ev)
    async with get_session_factory()() as s:
        repo = NotificationRepository(s, bid)
        notes = await repo.list_recent()
    assert len(notes) == 1
    assert notes[0].type == "low_stock"


async def test_low_stock_handler_skips_above_min():
    bid = await _make_business("b-ok")
    ev = Event(
        type=STOCK_ADJUSTED, business_id=bid,
        payload={"product_id": "p1", "new_quantity": 10, "min_quantity": 5},
    )
    await on_low_stock(ev)
    async with get_session_factory()() as s:
        repo = NotificationRepository(s, bid)
        notes = await repo.list_recent()
    assert len(notes) == 0
