from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.rbac import require_permission
from app.models import User
from app.schemas.products import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductListResponse, BarcodeLookupResponse, StockAdjustment,
)
from app.api.auth.dependencies import get_current_user
from app.repositories import ProductRepository

router = APIRouter(prefix="/products", tags=["Products"])


def _repo(db: AsyncSession, user: User) -> ProductRepository:
    return ProductRepository(db, user.business_id)


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    category: str = Query("", max_length=50),
    low_stock: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = _repo(db, user)
    products, total = await repo.list(
        page=page, per_page=per_page, search=search, category=category, low_stock=low_stock,
    )
    items = []
    for p in products:
        qty = await repo.inventory_quantity(p.id)
        p_dict = ProductResponse.model_validate(p).model_dump()
        p_dict["quantity"] = qty
        items.append(ProductResponse(**p_dict))
    return ProductListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/search/barcode", response_model=BarcodeLookupResponse)
async def lookup_barcode(
    barcode: str = Query(..., max_length=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await _repo(db, user).get_by_barcode(barcode)
    if product:
        return BarcodeLookupResponse(found=True, product=ProductResponse.model_validate(product))
    return BarcodeLookupResponse(found=False)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    req: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:create")),
):
    repo = _repo(db, user)
    product = await repo.create(
        name=req.name, name_sw=req.name_sw, barcode=req.barcode,
        category=req.category, unit=req.unit, price=req.price,
        cost_price=req.cost_price, tax_rate=req.tax_rate,
    )
    if req.quantity > 0:
        await repo.add_inventory_batch(
            product_id=product.id, quantity=req.quantity, min_quantity=req.min_quantity,
        )
    return ProductResponse.model_validate(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await _repo(db, user).get(product_id)
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
    repo = _repo(db, user)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found")
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.flush()
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:delete")),
):
    repo = _repo(db, user)
    product = await repo.get(product_id)
    if not product:
        raise NotFoundError("Product not found")
    product.is_active = False
    await db.flush()


@router.post("/stock/adjust", response_model=ProductResponse)
async def adjust_stock(
    req: StockAdjustment,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:stock_adjust")),
):
    repo = _repo(db, user)
    product = await repo.get(req.product_id)
    if not product:
        raise NotFoundError("Product not found")
    await repo.get_or_create_batch(product_id=product.id, quantity=req.quantity)
    return ProductResponse.model_validate(product)


@router.get("/categories/list")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"categories": await _repo(db, user).list_categories()}
