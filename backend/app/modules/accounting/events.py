"""Accounting module domain events (M3.1 convention; used by Phase 4 bus)."""
from __future__ import annotations

PAYMENT_CREATED = "accounting.payment.created"
PAYMENT_COMPLETED = "accounting.payment.completed"
PAYMENT_FAILED = "accounting.payment.failed"

__all__ = ["PAYMENT_CREATED", "PAYMENT_COMPLETED", "PAYMENT_FAILED"]
