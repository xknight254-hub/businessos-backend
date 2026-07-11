from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    type: str
    title: str
    message: str
    payload: str
    is_read: bool
    created_at: datetime
