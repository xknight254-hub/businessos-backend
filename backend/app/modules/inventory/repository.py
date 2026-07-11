"""Inventory repository (M3.2 / M3.1).

Encapsulates all product + inventory-batch DB access for the inventory
module. Real implementation lives here; `app.repositories.products`
re-exports it for backward compatibility.
"""
from __future__ import annotations

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, InventoryBatch, Branch


class ProductRepository:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id

    async def list(self, *, page: int = 1, per_page: int = 50,
                  search: str | None = None, category: str | None = None):
        query = select(Product).where(
            Product.business_id == self.business_id,
            Product.is_active == True,  # noqa: E712
        )
        if search:
            query = query.where(
                or_(Product.name.ilike(f"%{search}%"),
                     Product.barcode.ilike(f"%{search}%"))
            )
        if category:
            query = query.where(Product.category == category)
        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0
        result = await self.db.execute(
            query.order_by(Product.name)
            .offset((page - 1) * per_page).limit(per_page)
        )
        return result.scalars().all(), total

    async def low_stock(self):
        result = await self.db.execute(
            select(Product)
            .join(InventoryBatch, InventoryBatch.product_id == Product.id)
            .where(
                Product.business_id == self.business_id,
                InventoryBatch.quantity <= InventoryBatch.min_quantity,
            )
        )
        return result.scalars().all()

    async def get(self, product_id: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_barcode(self, barcode: str) -> Product | None:
        if not barcode:
            return None
        result = await self.db.execute(
            select(Product).where(
                Product.barcode == barcode,
                Product.business_id == self.business_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> Product:
        quantity = fields.pop("quantity", 0)
        min_quantity = fields.pop("min_quantity", 0)
        product = Product(business_id=self.business_id, **fields)
        self.db.add(product)
        await self.db.flush()
        branch = await self.first_branch()
        batch = InventoryBatch(
            business_id=self.business_id,
            branch_id=branch.id if branch else "",
            product_id=product.id,
            quantity=quantity,
            min_quantity=min_quantity,
        )
        self.db.add(batch)
        await self.db.flush()
        return product

    async def inventory_batch(self, product_id: str) -> InventoryBatch | None:
        result = await self.db.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.business_id == self.business_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def first_branch(self) -> Branch | None:
        result = await self.db.execute(
            select(Branch)
            .where(Branch.business_id == self.business_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_batch(self, product_id: str, branch_id: str | None,
                          quantity: int = 0) -> InventoryBatch:
        batch = InventoryBatch(
            business_id=self.business_id, branch_id=branch_id or "",
            product_id=product_id, quantity=quantity,
        )
        self.db.add(batch)
        await self.db.flush()
        return batch

    async def inventory_quantity(self, product_id: str) -> int:
        batch = await self.inventory_batch(product_id)
        return batch.quantity if batch else 0

    async def categories(self):
        result = await self.db.execute(
            select(Product.category)
            .where(
                Product.business_id == self.business_id,
                Product.is_active == True,  # noqa: E712
                Product.category.isnot(None),
            )
            .distinct()
        )
        return [r[0] for r in result.all() if r[0]]

    async def delete(self, product: Product) -> None:
        product.is_active = False
        await self.db.flush()
