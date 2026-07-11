"""Inventory module domain events (M3.1 convention; used by Phase 4 bus)."""
from __future__ import annotations

PRODUCT_CREATED = "inventory.product.created"
PRODUCT_UPDATED = "inventory.product.updated"
STOCK_ADJUSTED = "inventory.stock.adjusted"
LOW_STOCK = "inventory.stock.low"

__all__ = ["PRODUCT_CREATED", "PRODUCT_UPDATED", "STOCK_ADJUSTED", "LOW_STOCK"]
