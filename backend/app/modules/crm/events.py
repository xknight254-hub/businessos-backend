"""CRM module domain events (M3.1 convention; used by Phase 4 bus)."""
from __future__ import annotations

CUSTOMER_CREATED = "crm.customer.created"
CUSTOMER_UPDATED = "crm.customer.updated"
CREDIT_ADDED = "crm.credit.added"
CREDIT_PAID = "crm.credit.paid"

__all__ = ["CUSTOMER_CREATED", "CUSTOMER_UPDATED", "CREDIT_ADDED", "CREDIT_PAID"]
