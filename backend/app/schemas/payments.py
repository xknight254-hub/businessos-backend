from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StkPushRequest(BaseModel):
    phone: str
    amount: int  # in KES (not cents)
    sale_id: Optional[str] = None
    reference: str = "BusinessOS"


class StkPushResponse(BaseModel):
    merchant_request_id: Optional[str] = None
    checkout_request_id: Optional[str] = None
    response_code: str
    response_description: str
    is_mock: bool = False
    sale_id: Optional[str] = None


class MpesaCallback(BaseModel):
    """M-Pesa STK Push callback payload."""
    Body: dict


class PaymentConfirmation(BaseModel):
    merchant_request_id: str
    checkout_request_id: str
    result_code: int
    result_desc: str
    amount: Optional[float] = None
    mpesa_receipt_number: Optional[str] = None
    transaction_date: Optional[str] = None
    phone_number: Optional[str] = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sale_id: Optional[str] = None
    amount: int
    method: str
    reference: Optional[str] = None
    status: str
    created_at: datetime
