"""Messaging integrations (Phase 6 — M6.4 WhatsApp, M6.5 SMS).

Provider-agnostic gateways with a mock fallback so the system is fully
functional (and testable) without external credentials. When creds are
absent, providers run in mock mode and record the attempt instead of
calling a network API.
"""
from __future__ import annotations

import abc
import logging
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("businessos.messaging")


@dataclass
class SendResult:
    ok: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class SMSProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    async def send(self, to: str, message: str) -> SendResult:
        ...


class MockSMSProvider(SMSProvider):
    name = "mock"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, to: str, message: str) -> SendResult:
        self.sent.append((to, message))
        logger.info("sms_mock", extra={"to": to, "len": len(message)})
        return SendResult(ok=True, provider="mock", message_id=f"mock-{len(self.sent)}")


class AfricaTalkingProvider(SMSProvider):
    name = "africastalking"

    def __init__(self, username: str, api_key: str, sender_id: Optional[str]) -> None:
        self.username = username
        self.api_key = api_key
        self.sender_id = sender_id

    async def send(self, to: str, message: str) -> SendResult:
        # Africa's Talking REST: POST https://api.africastalking.com/version1/messaging
        # Real implementation would call the API; here we surface the
        # configured intent and require the network call to be wired.
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.africastalking.com/version1/messaging",
                    headers={"ApiKey": self.api_key, "Accept": "application/json"},
                    data={
                        "username": self.username,
                        "to": to,
                        "message": message,
                        **({"from": self.sender_id} if self.sender_id else {}),
                    },
                )
                resp.raise_for_status()
                return SendResult(ok=True, provider="africastalking", message_id=resp.json().get("SMSMessageData", {}).get("Recipients", [{}])[0].get("messageId"))
        except Exception as e:  # noqa: BLE001
            logger.error("sms_at_error", extra={"error": str(e)})
            return SendResult(ok=False, provider="africastalking", error=str(e))


def get_sms_provider() -> SMSProvider:
    if settings.SMS_PROVIDER == "africastalking" and settings.AFRICASTALKING_API_KEY:
        return AfricaTalkingProvider(
            settings.AFRICASTALKING_USERNAME or "sandbox",
            settings.AFRICASTALKING_API_KEY,
            settings.AFRICASTALKING_SENDER_ID,
        )
    return MockSMSProvider()


class WhatsAppProvider(abc.ABC):
    name = "base"

    @abc.abstractmethod
    async def send(self, to: str, message: str, template: Optional[str] = None) -> SendResult:
        ...


class MockWhatsAppProvider(WhatsAppProvider):
    name = "mock"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, to: str, message: str, template: Optional[str] = None) -> SendResult:
        self.sent.append((to, message))
        logger.info("whatsapp_mock", extra={"to": to, "template": template})
        return SendResult(ok=True, provider="mock", message_id=f"mock-wa-{len(self.sent)}")


class WhatsAppCloudProvider(WhatsAppProvider):
    name = "whatsapp_cloud"

    def __init__(self, token: str, phone_number_id: str) -> None:
        self.token = token
        self.phone_number_id = phone_number_id

    async def send(self, to: str, message: str, template: Optional[str] = None) -> SendResult:
        import httpx

        url = f"https://graph.facebook.com/v19.0/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                return SendResult(ok=True, provider="whatsapp_cloud", message_id=resp.json().get("messages", [{}])[0].get("id"))
        except Exception as e:  # noqa: BLE001
            logger.error("whatsapp_error", extra={"error": str(e)})
            return SendResult(ok=False, provider="whatsapp_cloud", error=str(e))


def get_whatsapp_provider() -> WhatsAppProvider:
    if settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        return WhatsAppCloudProvider(settings.WHATSAPP_API_TOKEN, settings.WHATSAPP_PHONE_NUMBER_ID)
    return MockWhatsAppProvider()
