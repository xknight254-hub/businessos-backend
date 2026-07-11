"""Backward-compat shim: real code moved to app.modules.sales.repository."""
from app.modules.sales.repository import SaleRepository

__all__ = ["SaleRepository"]
