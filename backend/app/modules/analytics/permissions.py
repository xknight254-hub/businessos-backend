"""Analytics module permissions (M3.3 skeleton)."""
from app.core.rbac import PERMISSIONS

ANALYTICS_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("analytics:")
}

__all__ = ["ANALYTICS_PERMISSIONS"]
