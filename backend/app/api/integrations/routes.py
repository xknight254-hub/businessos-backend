"""Kenya integrations endpoints (Phase 6 — M6.4 WhatsApp, M6.5 SMS).

Sends via provider-agnostic gateways. When credentials are absent the
providers run in mock mode, so the endpoints are fully exercisable in
dev/test without external accounts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.core.config import settings
from app.models import User
from app.services.messaging import get_sms_provider, get_whatsapp_provider, SendResult
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/integrations", tags=["integrations"])


class SendSMSRequest(BaseModel):
    to: str
    message: str


class SendWhatsAppRequest(BaseModel):
    to: str
    message: str
    template: str | None = None


class SendResponse(BaseModel):
    ok: bool
    provider: str
    message_id: str | None = None
    error: str | None = None
    mock: bool


def _to_response(r: SendResult, mock: bool) -> SendResponse:
    return SendResponse(ok=r.ok, provider=r.provider, message_id=r.message_id, error=r.error, mock=mock)


@router.post("/sms/send", response_model=SendResponse)
async def send_sms(
    req: SendSMSRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    provider = get_sms_provider()
    result = await provider.send(req.to, req.message)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.error)
    return _to_response(result, provider.name == "mock")


@router.post("/whatsapp/send", response_model=SendResponse)
async def send_whatsapp(
    req: SendWhatsAppRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    provider = get_whatsapp_provider()
    result = await provider.send(req.to, req.message, req.template)
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.error)
    return _to_response(result, provider.name == "mock")


@router.get("/status")
async def integration_status(user: User = Depends(get_current_user)):
    return {
        "sms_provider": settings.SMS_PROVIDER,
        "sms_configured": bool(settings.AFRICASTALKING_API_KEY),
        "whatsapp_configured": bool(settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID),
        "mpesa_configured": bool(settings.MPESA_CONSUMER_KEY),
        "etims_configured": bool(settings.ETIMS_API_KEY),
    }
