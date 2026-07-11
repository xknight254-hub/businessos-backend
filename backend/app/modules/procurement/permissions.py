"""Procurement module permissions (M3.3 skeleton)."""
from app.core.rbac import PERMISSIONS

PROCUREMENT_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("procurement:")
}

__all__ = ["PROCUREMENT_PERMISSIONS"]
