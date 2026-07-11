from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.core.rbac import require_permission
from app.models import User, Payment, Sale
from app.modules.accounting.schemas import (
    StkPushRequest, StkPushResponse, MpesaCallback, PaymentResponse,
)
from app.modules.accounting.repository import PaymentRepository
from app.modules.accounting.events import PAYMENT_COMPLETED
from app.core.events import event_bus, Event
from app.services.mpesa import MpesaClient
from app.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/payments", tags=["Payments"])
mpesa = MpesaClient()


def _repo(db: AsyncSession, user: User) -> PaymentRepository:
    return PaymentRepository(db, user.business_id)


@router.post("/mpesa/stk-push", response_model=StkPushResponse)
async def initiate_stk_push(
    req: StkPushRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("payment:create")),
):
    """Initiate M-Pesa STK Push payment."""
    if req.amount < 1:
        raise BadRequestError("Amount must be at least KES 1")

    result = await mpesa.stk_push(req.phone, req.amount, req.reference)
    response_code = result.get("ResponseCode", "1")
    is_success = response_code == "0"

    await _repo(db, user).create(
        sale_id=req.sale_id,
        amount=req.amount * 100,  # Convert to cents
        method="mpesa",
        reference=result.get("CheckoutRequestID", ""),
        status="pending" if is_success else "failed",
    )

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

        repo = PaymentRepository(db, business_id="")
        payment = await repo.get_by_reference(checkout_id)
        if not payment:
            return {"ResultCode": 0, "ResultDesc": "Accepted"}

        if result_code == 0:
            callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            mpesa_receipt = ""
            amount = 0
            for item in callback_metadata:
                name = item.get("Name", "")
                value = item.get("Value")
                if name == "MpesaReceiptNumber":
                    mpesa_receipt = str(value)
                elif name == "Amount":
                    amount = int(float(value))
            payment.status = "completed"
            payment.reference = mpesa_receipt or payment.reference

            await event_bus.publish(Event(
                type=PAYMENT_COMPLETED,
                business_id=payment.business_id,
                payload={
                    "payment_id": payment.id,
                    "amount": payment.amount,
                    "sale_id": payment.sale_id,
                    "mpesa_receipt": mpesa_receipt,
                },
            ))

            if payment.sale_id:
                sale = await repo.get_sale(payment.sale_id)
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
    payment = await _repo(db, user).get_by_reference(checkout_request_id)
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
    payments = await PaymentRepository(db, user.business_id).list_recent(20)
    return {"items": [PaymentResponse.model_validate(p) for p in payments]}
