"""Role-Based Access Control for BusinessOS.

Builds on the existing ``User.role`` (owner / manager / staff).

Two layers:
1. ``require_role(*roles)`` — already in ``auth/dependencies.py``; keep for
   coarse checks.
2. ``require_permission("product:delete")`` — fine-grained, backed by the
   ``PERMISSIONS`` map below. Unknown permission -> 403.

The map is the single source of truth. Extend it per module as Phase 3
lands (each module gets its own ``permissions.py`` eventually; this is the
central interim registry).
"""
from __future__ import annotations

from fastapi import Depends
from app.api.auth.dependencies import get_current_user
from app.core.exceptions import ForbiddenError
from app.models import User

# Permission string -> set of roles allowed.
# Resource names mirror the API prefixes (products, customers, sales, ...).
PERMISSIONS: dict[str, set[str]] = {
    # Products
    "product:create": {"owner", "manager", "staff"},
    "product:read": {"owner", "manager", "staff"},
    "product:update": {"owner", "manager", "staff"},
    "product:delete": {"owner"},  # destructive -> owner only
    "product:stock_adjust": {"owner", "manager", "staff"},
    # Customers
    "customer:create": {"owner", "manager", "staff"},
    "customer:read": {"owner", "manager", "staff"},
    "customer:update": {"owner", "manager", "staff"},
    "customer:delete": {"owner"},
    "customer:credit": {"owner", "manager"},  # money movement -> not staff
    # Sales
    "sale:create": {"owner", "manager", "staff"},
    "sale:read": {"owner", "manager", "staff"},
    "sale:void": {"owner", "manager"},
    # Payments
    "payment:create": {"owner", "manager", "staff"},
    "payment:read": {"owner", "manager", "staff"},
    # Reports / AI / automation / partner
    "report:read": {"owner", "manager"},
    "ai:use": {"owner", "manager", "staff"},
    "automation:manage": {"owner", "manager"},
    "partner:chat": {"owner", "manager", "staff"},
    # Business admin (owner-level)
    "business:manage": {"owner"},
    "user:manage": {"owner", "manager"},
}


def require_permission(permission: str):
    """Dependency factory: enforce a fine-grained permission on a route.

    Usage::

        @router.delete("/{product_id}")
        async def delete_product(
            product_id: str,
            user: User = Depends(require_permission("product:delete")),
        ):
            ...
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        allowed = PERMISSIONS.get(permission)
        if allowed is None:
            # Unknown permission is treated as deny-by-default (fail closed).
            raise ForbiddenError(f"Permission '{permission}' is not defined")
        if user.role not in allowed:
            raise ForbiddenError(
                f"Role '{user.role}' lacks permission '{permission}'. "
                f"Required: {sorted(allowed)}"
            )
        return user

    return _check


def role_can(role: str, permission: str) -> bool:
    """Pure helper for tests / UI permission hints."""
    allowed = PERMISSIONS.get(permission)
    return allowed is not None and role in allowed
