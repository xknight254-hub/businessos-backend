"""Payroll module permissions (M3.3 skeleton)."""
from app.core.rbac import PERMISSIONS

PAYROLL_PERMISSIONS = {
    k: v for k, v in PERMISSIONS.items() if k.startswith("payroll:")
}

__all__ = ["PAYROLL_PERMISSIONS"]
