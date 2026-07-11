"""Audit logging for BusinessOS.

Provides:
- ``write_audit``: low-level insert of an ``AuditLog`` row (awaitable).
- ``AuditMiddleware``: captures mutating requests (POST/PUT/PATCH/DELETE)
  and records them with the acting user (from the bearer token ``sub``),
  the route path, and client IP. Best-effort: audit failure must never
  break the business request.

The ``AuditLog`` model already exists
(``business_id`` required) — so we resolve ``business_id`` from the
token payload (``business_id`` claim set at login) when present.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.core.security import decode_token
from app.models import AuditLog

logger = get_logger("businessos.audit")


async def write_audit(
    *,
    business_id: str,
    user_id: Optional[str],
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Insert an audit row. Swallows all errors so auditing never 5xx's a request."""
    try:
        factory: sessionmaker = get_session_factory()
        async with factory() as session:
            row = AuditLog(
                id=str(uuid.uuid4()),
                business_id=business_id,
                user_id=user_id,
                action=action,
                resource=resource,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:  # pragma: no cover - audit must be non-fatal
        logger.warning("audit_write_failed", extra={"detail": str(exc)})


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    return (request.client.host if request.client else None)


async def audit_middleware(request: Request, call_next):
    """Record mutating requests. Runs after the handler so we know the outcome."""
    response = await call_next(request)
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return response
    try:
        auth = request.headers.get("authorization", "")
        user_id = None
        business_id = None
        if auth.lower().startswith("bearer "):
            payload = decode_token(auth[7:].strip())
            user_id = payload.get("sub")
            business_id = payload.get("business_id")
        if not business_id:
            # Unauthenticated mutating call (e.g. public endpoint) - skip detailed audit
            # but still note the attempt at route level if a business can be inferred.
            return response
        action = request.method.lower()
        resource = request.url.path.strip("/").split("/")[0] or "unknown"
        await write_audit(
            business_id=business_id,
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=None,
            details=f"{request.method} {request.url.path} -> {response.status_code}",
            ip_address=_client_ip(request),
        )
    except Exception as exc:  # pragma: no cover - never break the request
        logger.warning("audit_middleware_error", extra={"detail": str(exc)})
    return response
