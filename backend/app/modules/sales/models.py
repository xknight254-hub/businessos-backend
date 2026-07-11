"""Sales module models — re-export the slice owned by this module."""
from app.models import Sale, SaleItem

__all__ = ["Sale", "SaleItem"]
