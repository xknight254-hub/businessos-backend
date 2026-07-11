"""Event-driven side-effect handlers (Phase 4 — M4.3).

Each handler subscribes to a canonical event and performs a side effect
(currently: writing a Notification row). Handlers receive only the Event;
they open their own DB session via the shared async_session factory, so they
work regardless of which request published the event.

Handlers are idempotent-by-construction: a notification is created per
event. For true dedup (e.g. at-most-once across retries) key on
event_id in later phases.
"""
from __future__ import annotations

from app.core.database import get_session_factory
from app.core.events import Event, event_bus
from app.core.logging import get_logger
from app.modules.notifications.repository import NotificationRepository

logger = get_logger("businessos.handlers")


async def on_payment_completed(event: Event) -> None:
    p = event.payload
    if p.get("amount") is None:
        return
    amount_sh = p["amount"] / 100  # cents -> KES
    async with get_session_factory()() as session:
        repo = NotificationRepository(session, event.business_id)
        await repo.create(
            type="payment_received",
            title="Payment received",
            message=f"KES {amount_sh:,.0f} received"
            + (f" (M-Pesa {p.get('mpesa_receipt')})" if p.get("mpesa_receipt") else ""),
            payload=p,
        )
        await session.commit()


async def on_low_stock(event: Event) -> None:
    p = event.payload
    new_qty = p.get("new_quantity", 0)
    min_qty = p.get("min_quantity", 0)
    if new_qty > min_qty:
        return  # still above threshold; not a low-stock event
    async with get_session_factory()() as session:
        repo = NotificationRepository(session, event.business_id)
        await repo.create(
            type="low_stock",
            title="Low stock alert",
            message=f"Product {p.get('product_id')} is at {new_qty} "
                    f"(min {min_qty}).",
            payload=p,
        )
        await session.commit()


def register_handlers() -> None:
    """Wire handlers to the shared bus. Call once at startup."""
    event_bus.subscribe("accounting.payment.completed", on_payment_completed)
    event_bus.subscribe("inventory.stock.adjusted", on_low_stock)
    logger.info("event_handlers_registered")
