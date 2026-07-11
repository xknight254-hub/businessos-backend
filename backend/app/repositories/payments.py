"""Backward-compat shim: real code moved to app.modules.accounting.repository."""
from app.modules.accounting.repository import PaymentRepository

__all__ = ["PaymentRepository"]
