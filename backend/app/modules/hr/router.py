"""hr module router (M3.3 skeleton)."""
from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/hr", tags=["Hr"])


@router.get("/health")
async def health(user: User = Depends(get_current_user)):
    return {"module": "hr", "status": "ok"}
