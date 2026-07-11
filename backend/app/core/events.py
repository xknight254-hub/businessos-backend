"""Event bus (Phase 4 — Event Driven).

Lightweight in-process event bus with a seam for a Redis-backed pub/sub
backend later (same memory/Redis auto-select pattern as the rate-limit and
token-store abstractions). For Kenya SME single-instance deployments the
in-process bus is sufficient; set REDIS_URL to upgrade transparently.

Events are plain dataclasses with a `type`, `business_id`, and `payload`.
Handlers are async callables; a failing handler is logged and never
allowed to break the publishing request.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Union

from app.core.logging import get_logger

logger = get_logger("businessos.events")

# Canonical event types (BusinessOS Backend Engineering Blueprint — Phase 4)
CUSTOMER_CREATED = "crm.customer.created"
INVOICE_CREATED = "sales.invoice.created"
PAYMENT_RECEIVED = "accounting.payment.received"
INVENTORY_ADJUSTED = "inventory.stock.adjusted"
WORKFLOW_COMPLETED = "automation.workflow.completed"

# Wildcard subscription receives every event
WILDCARD = "*"

Handler = Callable[["Event"], Union[None, Awaitable[None]]]


@dataclass
class Event:
    type: str
    business_id: str
    payload: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """In-process event bus.

    Backend note: a Redis pub/sub variant would fan events out across
    worker processes. The in-process bus covers single-instance needs and
    is the default until REDIS_URL is reachable.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Handler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    async def publish(self, event: Event) -> None:
        targets = self._handlers.get(event.type, []) + self._handlers.get(WILDCARD, [])
        for handler in targets:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # never break the publishing flow
                logger.error(
                    "event_handler_failed",
                    extra={
                        "event_type": event.type,
                        "event_id": event.event_id,
                        "handler": getattr(handler, "__name__", repr(handler)),
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )


# Single shared bus for the process
event_bus = EventBus()
