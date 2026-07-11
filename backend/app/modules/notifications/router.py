from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import User
from app.modules.notifications.schemas import NotificationResponse
from app.modules.notifications.repository import NotificationRepository
from app.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List recent notifications for the business (M4.3)."""
    repo = NotificationRepository(db, user.business_id)
    notifications = await repo.list_recent(50)
    return [NotificationResponse.model_validate(n) for n in notifications]
