"""Customer (CRM) repository (M3.2).

Encapsulates all customer DB access. Routers/services depend on this,
never on the raw session.
"""
from __future__ import annotations

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer


class CustomerRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def list(self, *, page: int = 1, per_page: int = 20, search: str = ""):
        query = select(Customer).where(Customer.business_id == self.business_id)
        if search:
            query = query.where(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.phone.ilike(f"%{search}%"),
                )
            )
        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(Customer.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return result.scalars().all(), total

    async def get_by_phone(self, phone: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(
                Customer.phone == phone,
                Customer.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def get(self, customer_id: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> Customer:
        customer = Customer(business_id=self.business_id, **fields)
        self.db.add(customer)
        await self.db.flush()
        return customer
