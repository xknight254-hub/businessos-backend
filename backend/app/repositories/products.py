"""Backward-compat shim: real code moved to app.modules.inventory.repository."""
from app.modules.inventory.repository import ProductRepository

__all__ = ["ProductRepository"]
