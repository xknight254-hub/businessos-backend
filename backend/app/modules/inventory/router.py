"""Inventory module (M3.1/M3.3).

Canonical module package: router / schemas / repository / models / permissions /
tasks / events / tests. Real code lives here; `app.schemas.products` and
`app.repositories.products` are thin re-export shims for backward compat.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError
from app.core.rbac import require_permission
from app.models import User, Product, InventoryBatch, Branch
from app.modules.inventory.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    BarcodeLookupResponse, StockAdjustment,
)
from app.modules.inventory.repository import ProductRepository
from app.modules.inventory.events import PRODUCT_CREATED, STOCK_ADJUSTED
from app.core.events import event_bus, Event
from app.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: str = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = ProductRepository(db, user.business_id)
    products, total = await repo.list(
        page=page, per_page=per_page, search=search, category=category,
    )
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total, page=page, per_page=per_page,
    )


@router.get("/low-stock", response_model=list[ProductResponse])
async def low_stock_products(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = ProductRepository(db, user.business_id)
    products = await repo.low_stock()
    return [ProductResponse.model_validate(p) for p in products]


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    req: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:create")),
):
    repo = ProductRepository(db, user.business_id)
    existing = await repo.get_by_barcode(req.barcode) if req.barcode else None
    if existing:
        raise ConflictError(f"Product with barcode {req.barcode} already exists")
    product = await repo.create(
        name=req.name, name_sw=req.name_sw, barcode=req.barcode,
        category=req.category, unit=req.unit, price=req.price,
        cost_price=req.cost_price, tax_rate=req.tax_rate, quantity=req.quantity,
        min_quantity=req.min_quantity,
    )
    await db.flush()
    await event_bus.publish(Event(
        type=PRODUCT_CREATED,
        business_id=user.business_id,
        payload={"product_id": product.id, "name": product.name, "barcode": product.barcode},
    ))
    return ProductResponse.model_validate(product)


@router.get("/search/barcode", response_model=BarcodeLookupResponse)
async def barcode_lookup(
    barcode: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = ProductRepository(db, user.business_id)
    product = await repo.get_by_barcode(barcode)
    return BarcodeLookupResponse(
        found=product is not None,
        product=ProductResponse.model_validate(product) if product else None,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = ProductRepository(db, user.business_id)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found")
    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    req: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:update")),
):
    repo = ProductRepository(db, user.business_id)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found")
    update_fields = req.model_dump(exclude_unset=True)
    if "quantity" in update_fields:
        update_fields.pop("quantity")
    for field, value in update_fields.items():
        setattr(product, field, value)
    await db.flush()
    return ProductResponse.model_validate(product)


@router.post("/stock/adjust", response_model=ProductResponse)
async def adjust_stock(
    req: StockAdjustment,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:stock_adjust")),
):
    repo = ProductRepository(db, user.business_id)
    product = await repo.get(req.product_id)
    if not product:
        raise NotFoundError("Product not found")
    batch = await repo.inventory_batch(req.product_id)
    if batch is None:
        branch = await repo.first_branch()
        batch = await repo.create_batch(req.product_id, branch.id if branch else None)
    batch.quantity += req.quantity
    if batch.quantity < 0:
        raise BadRequestError("Insufficient stock")
    await db.flush()
    await event_bus.publish(Event(
        type=STOCK_ADJUSTED,
        business_id=user.business_id,
        payload={
            "product_id": req.product_id, "quantity": req.quantity,
            "new_quantity": batch.quantity, "min_quantity": batch.min_quantity,
        },
    ))
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:delete")),
):
    repo = ProductRepository(db, user.business_id)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found")
    await repo.delete(product)
    await db.flush()


@router.get("/categories/list")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = ProductRepository(db, user.business_id)
    categories = await repo.categories()
    return {"categories": categories}
