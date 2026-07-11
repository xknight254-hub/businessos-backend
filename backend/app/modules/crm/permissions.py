"""CRM module permissions — slice of the global PERMISSIONS map."""
from app.core.rbac import PERMISSIONS

CRM_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("customer:")
}

__all__ = ["CRM_PERMISSIONS"]
