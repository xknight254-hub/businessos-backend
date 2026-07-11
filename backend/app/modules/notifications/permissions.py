"""Notifications module permissions (M3.3 skeleton)."""
from app.core.rbac import PERMISSIONS

NOTIFICATIONS_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("notifications:")
}

__all__ = ["NOTIFICATIONS_PERMISSIONS"]
