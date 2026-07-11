"""Inventory module models — re-export the slice owned by this module."""
from app.models import Product, InventoryBatch

__all__ = ["Product", "InventoryBatch"]
