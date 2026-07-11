"""M-Pesa Daraja API integration layer."""
import base64
import hashlib
import json
import httpx
from datetime import datetime
from app.core.config import settings


class MpesaClient:
    """Client for Safaricom Daraja API (STK Push, C2B, B2C, reconciliation)."""

    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY or "test_key"
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET or "test_secret"
        self.passkey = settings.MPESA_PASSKEY or "test_passkey"
        self.shortcode = settings.MPESA_SHORTCODE or "174379"  # sandbox default
        self.environment = settings.MPESA_ENVIRONMENT  # "sandbox" or "production"
        self._access_token = None
        self._token_expiry = None

    @property
    def base_url(self):
        if self.environment == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @property
    def is_mock(self) -> bool:
        """Returns True if running without real Daraja credentials."""
        return settings.MPESA_CONSUMER_KEY is None or settings.MPESA_CONSUMER_KEY == "test_key"

    async def get_token(self) -> str:
        """Get OAuth access token from Daraja."""
        if self._access_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return self._access_token

        if self.is_mock:
            self._access_token = "mock_token"
            return self._access_token

        auth = base64.b64encode(
            f"{self.consumer_key}:{self.consumer_secret}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {auth}"},
            )
            data = response.json()
            self._access_token = data.get("access_token", "")
            expires_in = data.get("expires_in", 3600)
            from datetime import timedelta
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            return self._access_token

    def _generate_password(self, timestamp: str) -> str:
        """Generate STK Push password: base64(shortcode + passkey + timestamp)."""
        to_encode = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(to_encode.encode()).decode()

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S")

    async def stk_push(self, phone: str, amount: int, reference: str = "BusinessOS") -> dict:
        """Initiate STK Push (Lipa na M-Pesa Online)."""
        timestamp = self._timestamp()
        password = self._generate_password(timestamp)

        # Format phone: 254XXXXXXXX
        phone = phone.strip()
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": self.shortcode,
            "PhoneNumber": phone,
            "CallBackURL": f"{settings.API_BASE_URL or 'http://localhost:8000'}/api/v1/payments/mpesa/callback",
            "AccountReference": reference[:12],
            "TransactionDesc": "BusinessOS Payment",
        }

        if self.is_mock:
            return {
                "MerchantRequestID": "mock-request-id",
                "CheckoutRequestID": "mock-checkout-id",
                "ResponseCode": "0",
                "ResponseDescription": "Success. Mock mode.",
                "is_mock": True,
            }

        token = await self.get_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.json()

    async def query_status(self, checkout_request_id: str) -> dict:
        """Query STK Push transaction status."""
        timestamp = self._timestamp()
        password = self._generate_password(timestamp)

        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        if self.is_mock:
            return {
                "ResponseCode": "0",
                "ResultCode": "0",
                "ResultDesc": "Transaction completed successfully (mock)",
            }

        token = await self.get_token()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.json()
