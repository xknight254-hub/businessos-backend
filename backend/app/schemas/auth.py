from pydantic import BaseModel, Field
from typing import Optional


class PhoneAuthRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+?254\d{9}$")


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


class PinSetupRequest(BaseModel):
    phone: str
    pin: str = Field(..., min_length=4, max_length=6)
    business_name: str
    business_type: str


class LoginRequest(BaseModel):
    phone: str
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    business_id: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str
