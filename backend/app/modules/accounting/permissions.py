"""Accounting module permissions — slice of the global PERMISSIONS map."""
from app.core.rbac import PERMISSIONS

ACCOUNTING_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("payment:")
}

__all__ = ["ACCOUNTING_PERMISSIONS"]
