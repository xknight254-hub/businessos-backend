"""CRM repository (M3.2 / M3.1)."""
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer


class CustomerRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def list(self, *, page: int = 1, per_page: int = 50,
                  search: str | None = None):
        query = select(Customer).where(Customer.business_id == self.business_id)
        if search:
            query = query.where(Customer.name.ilike(f"%{search}%"))
        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(Customer.name)
            .offset((page - 1) * per_page).limit(per_page)
        )
        return result.scalars().all(), total

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

    async def adjust_credit(self, customer: Customer, delta: int) -> None:
        new_balance = customer.credit_balance + delta
        if new_balance > customer.credit_limit:
            raise ValueError("Credit limit exceeded")
        customer.credit_balance = new_balance
        await self.db.flush()

    async def pay_credit(self, customer: Customer, amount: int) -> None:
        customer.credit_balance = max(0, customer.credit_balance - amount)
        await self.db.flush()
