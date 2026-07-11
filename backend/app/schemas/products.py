"""Backward-compat shim: real code moved to app.modules.inventory.schemas."""
from app.modules.inventory.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    BarcodeLookupResponse, StockAdjustment,
)

__all__ = [
    "ProductCreate", "ProductUpdate", "ProductResponse", "ProductListResponse",
    "BarcodeLookupResponse", "StockAdjustment",
]
