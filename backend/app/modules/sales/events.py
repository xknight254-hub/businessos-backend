"""Sales module domain events (M3.1 convention; used by Phase 4 bus)."""
from __future__ import annotations

SALE_CREATED = "sales.sale.created"
SALE_VOIDED = "sales.sale.voided"
SALE_PAID = "sales.sale.paid"

__all__ = ["SALE_CREATED", "SALE_VOIDED", "SALE_PAID"]
