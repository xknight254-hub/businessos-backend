"""Product/inventory repository (M3.2).

Encapsulates all product + inventory-batch DB access. Routers and
services depend on this, never on the raw session. Keeping DB access
here is the blueprint's coding standard: "repositories only access DB".
"""
from __future__ import annotations

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, InventoryBatch


class ProductRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def list(
        self, *, page: int = 1, per_page: int = 20,
        search: str = "", category: str = "", low_stock: bool = False,
    ):
        query = select(Product).where(
            Product.business_id == self.business_id,
            Product.is_active == True,  # noqa: E712
        )
        if search:
            query = query.where(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.barcode.ilike(f"%{search}%"),
                )
            )
        if category:
            query = query.where(Product.category == category)
        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(Product.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return result.scalars().all(), total

    async def get_by_barcode(self, barcode: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.barcode == barcode,
                Product.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def get(self, product_id: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> Product:
        product = Product(business_id=self.business_id, **fields)
        self.db.add(product)
        await self.db.flush()
        return product

    async def add_inventory_batch(self, *, product_id: str, quantity: int, min_quantity: int = 0):
        batch = InventoryBatch(
            business_id=self.business_id,
            branch_id="",  # set when branch system is complete
            product_id=product_id,
            quantity=quantity,
            min_quantity=min_quantity,
        )
        self.db.add(batch)
        await self.db.flush()
        return batch

    async def inventory_quantity(self, product_id: str) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(InventoryBatch.quantity), 0)).where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.business_id == self.business_id,
            )
        )
        return int(result.scalar() or 0)

    async def get_or_create_batch(self, *, product_id: str, quantity: int) -> InventoryBatch:
        result = await self.db.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.business_id == self.business_id,
            )
            .limit(1)
        )
        batch = result.scalar_one_or_none()
        if batch:
            batch.quantity += quantity
        else:
            batch = InventoryBatch(
                business_id=self.business_id,
                branch_id="",
                product_id=product_id,
                quantity=max(0, quantity),
            )
            self.db.add(batch)
        await self.db.flush()
        return batch

    async def list_categories(self):
        result = await self.db.execute(
            select(Product.category, func.count(Product.id))
            .where(
                Product.business_id == self.business_id,
                Product.is_active == True,  # noqa: E712
                Product.category.isnot(None),
            )
            .group_by(Product.category)
            .order_by(Product.category)
        )
        return [{"name": row[0], "count": row[1]} for row in result.all()]
