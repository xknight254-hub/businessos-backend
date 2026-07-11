"""Backward-compat shim: real code moved to app.modules.accounting.schemas."""
from app.modules.accounting.schemas import (
    StkPushRequest, StkPushResponse, MpesaCallback, PaymentConfirmation,
    PaymentResponse,
)

__all__ = [
    "StkPushRequest", "StkPushResponse", "MpesaCallback",
    "PaymentConfirmation", "PaymentResponse",
]
