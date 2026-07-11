"""Procurement module repository (M3.3 skeleton)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class PROCUREMENTRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id
