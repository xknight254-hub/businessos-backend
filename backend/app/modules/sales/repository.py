"""Sale (sales) repository (M3.2 / M3.1)."""
from __future__ import annotations

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Sale, SaleItem, Payment, Product, InventoryBatch, Customer


class SaleRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def get_product(self, product_id: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.business_id == self.business_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def create_sale(self, **fields) -> Sale:
        sale = Sale(business_id=self.business_id, **fields)
        self.db.add(sale)
        await self.db.flush()
        return sale

    async def create_sale_item(self, **fields) -> SaleItem:
        item = SaleItem(**fields)
        self.db.add(item)
        await self.db.flush()
        return item

    async def create_payment(self, **fields) -> Payment:
        payment = Payment(**fields)
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def get_inventory_batch(self, product_id: str) -> InventoryBatch | None:
        result = await self.db.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.business_id == self.business_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_customer(self, customer_id: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def list(self, *, page: int = 1, per_page: int = 20,
                  date_from=None, date_to=None):
        query = select(Sale).where(Sale.business_id == self.business_id)
        if date_from:
            query = query.where(Sale.created_at >= date_from)
        if date_to:
            query = query.where(Sale.created_at <= date_to)
        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(desc(Sale.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return result.scalars().all(), total

    async def get(self, sale_id: str) -> Sale | None:
        result = await self.db.execute(
            select(Sale).where(
                Sale.id == sale_id,
                Sale.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_day(self, day_start, day_end):
        result = await self.db.execute(
            select(Sale).where(
                Sale.business_id == self.business_id,
                Sale.created_at >= day_start,
                Sale.created_at < day_end,
                Sale.status == "completed",
            )
        )
        return result.scalars().all()

    async def top_products(self, day_start, day_end, limit: int = 5):
        result = await self.db.execute(
            select(
                Product.name, func.sum(SaleItem.quantity).label("qty"),
                func.sum(SaleItem.total).label("rev"),
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.business_id == self.business_id,
                Sale.created_at >= day_start,
                Sale.created_at < day_end,
            )
            .group_by(Product.name)
            .order_by(desc("rev"))
            .limit(limit)
        )
        return [{"name": r[0], "quantity": r[1], "revenue": r[2]} for r in result.all()]

    async def get_items(self, sale_id: str):
        result = await self.db.execute(
            select(SaleItem, Product.name)
            .join(Product, SaleItem.product_id == Product.id)
            .where(SaleItem.sale_id == sale_id)
        )
        return result.all()

    async def get_payments(self, sale_id: str):
        result = await self.db.execute(
            select(Payment).where(Payment.sale_id == sale_id)
        )
        return result.scalars().all()
