"""Sales module permissions — slice of the global PERMISSIONS map."""
from app.core.rbac import PERMISSIONS

SALES_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("sale:")
}

__all__ = ["SALES_PERMISSIONS"]
