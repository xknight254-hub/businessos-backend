from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models import Payment, Sale, User
from app.schemas.payments import (
    StkPushRequest, StkPushResponse, MpesaCallback, PaymentConfirmation, PaymentResponse,
)
from app.api.auth.dependencies import get_current_user
from app.services.mpesa import MpesaClient
from typing import Optional
from datetime import datetime, timezone
import json

router = APIRouter(prefix="/payments", tags=["Payments"])
mpesa = MpesaClient()


@router.post("/mpesa/stk-push", response_model=StkPushResponse)
async def initiate_stk_push(
    req: StkPushRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Initiate M-Pesa STK Push payment."""
    if req.amount < 1:
        raise HTTPException(status_code=400, detail="Amount must be at least KES 1")
    
    # Initiate STK Push
    result = await mpesa.stk_push(req.phone, req.amount, req.reference)
    
    response_code = result.get("ResponseCode", "1")
    is_success = response_code == "0"
    
    # Record the payment attempt
    payment = Payment(
        sale_id=req.sale_id,
        amount=req.amount * 100,  # Convert to cents
        method="mpesa",
        reference=result.get("CheckoutRequestID", ""),
        status="pending" if is_success else "failed",
    )
    db.add(payment)
    await db.flush()
    
    return StkPushResponse(
        merchant_request_id=result.get("MerchantRequestID"),
        checkout_request_id=result.get("CheckoutRequestID"),
        response_code=response_code,
        response_description=result.get("ResponseDescription", "Failed"),
        is_mock=result.get("is_mock", False),
        sale_id=req.sale_id,
    )


@router.post("/mpesa/callback")
async def mpesa_callback(
    callback: MpesaCallback,
    db: AsyncSession = Depends(get_db),
):
    """M-Pesa STK Push callback endpoint."""
    try:
        stk_callback = callback.Body.get("stkCallback", {})
        checkout_id = stk_callback.get("CheckoutRequestID", "")
        result_code = stk_callback.get("ResultCode", 1)
        result_desc = stk_callback.get("ResultDesc", "")
        
        # Find the pending payment
        payment_result = await db.execute(
            select(Payment).where(Payment.reference == checkout_id)
        )
        payment = payment_result.scalar_one_or_none()
        if not payment:
            return {"ResultCode": 0, "ResultDesc": "Accepted"}
        
        if result_code == 0:
            # Successful payment
            callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            mpesa_receipt = ""
            amount = 0
            phone = ""
            tx_date = ""
            
            for item in callback_metadata:
                name = item.get("Name", "")
                value = item.get("Value")
                if name == "MpesaReceiptNumber":
                    mpesa_receipt = str(value)
                elif name == "Amount":
                    amount = int(float(value))
                elif name == "PhoneNumber":
                    phone = str(value)
                elif name == "TransactionDate":
                    tx_date = str(value)
            
            payment.status = "completed"
            payment.reference = mpesa_receipt or payment.reference
            
            # If linked to a sale, update sale payment method
            if payment.sale_id:
                sale_result = await db.execute(
                    select(Sale).where(Sale.id == payment.sale_id)
                )
                sale = sale_result.scalar_one_or_none()
                if sale:
                    sale.payment_method = "mpesa"
        else:
            payment.status = "failed"
        
        await db.flush()
    except Exception:
        pass  # Always return success to M-Pesa
    
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/mpesa/query/{checkout_request_id}")
async def query_payment_status(
    checkout_request_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Query the status of an STK Push transaction."""
    result = await mpesa.query_status(checkout_request_id)
    
    # Update payment status
    payment_result = await db.execute(
        select(Payment).where(Payment.reference == checkout_request_id)
    )
    payment = payment_result.scalar_one_or_none()
    if payment:
        if result.get("ResultCode") == "0":
            payment.status = "completed"
        elif result.get("ResultCode") != "0":
            payment.status = "failed"
        await db.flush()
    
    return result


@router.get("/history")
async def payment_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent payments for the business."""
    result = await db.execute(
        select(Payment).where(Payment.id.isnot(None))
        .order_by(Payment.created_at.desc())
        .limit(20)
    )
    payments = result.scalars().all()
    return {"items": [PaymentResponse.model_validate(p) for p in payments]}
