"""Notification repository (M4.3)."""
from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def create(
        self, type: str, title: str, message: str, payload: dict | None = None
    ) -> Notification:
        n = Notification(
            business_id=self.business_id,
            type=type,
            title=title,
            message=message,
            payload=json.dumps(payload or {}),
        )
        self.db.add(n)
        await self.db.flush()
        return n

    async def list_recent(self, limit: int = 50) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.business_id == self.business_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
