"""Payment (accounting) repository (M3.2 / M3.1)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Sale


class PaymentRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def create(self, **fields) -> Payment:
        payment = Payment(**fields)
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def get_by_reference(self, reference: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.reference == reference)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, payment_id: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_sale(self, sale_id: str) -> Sale | None:
        result = await self.db.execute(
            select(Sale).where(Sale.id == sale_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20):
        result = await self.db.execute(
            select(Payment)
            .where(Payment.id.isnot(None))
            .order_by(Payment.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
