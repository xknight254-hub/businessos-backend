"""Hr module permissions (M3.3 skeleton)."""
from app.core.rbac import PERMISSIONS

HR_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("hr:")
}

__all__ = ["HR_PERMISSIONS"]
