from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_pin, verify_pin, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import ConflictError, BusinessError
from app.core.logging import get_logger
from app.models import Business, User
from app.schemas.auth import (
    PhoneAuthRequest, VerifyCodeRequest, PinSetupRequest,
    LoginRequest, TokenResponse, RefreshRequest,
)
from app.api.auth.dependencies import get_current_user
import random

logger = get_logger("businessos.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory SMS code store (replace with Redis in production)
_sms_codes: dict = {}


@router.post("/send-code")
async def send_code(req: PhoneAuthRequest):
    code = str(random.randint(100000, 999999))
    _sms_codes[req.phone] = code
    logger.info("sms_code_issued", extra={"phone": req.phone})
    return {"message": "Code sent", "expires_in": 300}


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest):
    stored = _sms_codes.get(req.phone)
    if not stored or stored != req.code:
        raise BusinessError("Invalid or expired code", code="invalid_code", status_code=400)
    del _sms_codes[req.phone]
    return {"message": "Phone verified", "phone": req.phone}


@router.post("/register", response_model=TokenResponse)
async def register(req: PinSetupRequest, db: AsyncSession = Depends(get_db)):
    # Check if phone already exists
    result = await db.execute(select(Business).where(Business.phone == req.phone))
    if result.scalar_one_or_none():
        raise ConflictError("Phone already registered")
    
    # Create business
    business = Business(name=req.business_name, type=req.business_type, phone=req.phone)
    db.add(business)
    await db.flush()
    
    # Create default branch
    from app.models import Branch
    branch = Branch(business_id=business.id, name="Main Branch", phone=req.phone)
    db.add(branch)
    
    # Create owner user
    user = User(
        business_id=business.id,
        name="Owner",
        phone=req.phone,
        pin_hash=hash_pin(req.pin),
        role="owner",
    )
    db.add(user)
    await db.flush()
    
    access = create_access_token({"sub": user.id, "business_id": business.id, "role": "owner"})
    refresh = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        business_id=business.id,
        role="owner",
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.phone == req.phone, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_pin(req.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access = create_access_token({"sub": user.id, "business_id": user.business_id, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        business_id=user.business_id,
        role=user.role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    access = create_access_token({"sub": user.id, "business_id": user.business_id, "role": user.role})
    refresh = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user_id=user.id,
        business_id=user.business_id,
        role=user.role,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "role": user.role,
        "business_id": user.business_id,
        "biometric_enabled": user.biometric_enabled,
    }
