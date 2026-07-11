from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError, ForbiddenError, UnauthorizedError
from app.core.rbac import require_permission
from app.models import Product, InventoryBatch
from app.schemas.products import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductListResponse, BarcodeLookupResponse, StockAdjustment,
)
from app.api.auth.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/products", tags=["Products"])


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
    query = select(Product).where(
        Product.business_id == user.business_id,
        Product.is_active == True,
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
    
    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    
    # Paginate
    result = await db.execute(
        query.order_by(Product.name).offset((page - 1) * per_page).limit(per_page)
    )
    products = result.scalars().all()
    
    # Enrich with inventory quantity
    items = []
    for p in products:
        inv_q = await db.execute(
            select(func.coalesce(func.sum(InventoryBatch.quantity), 0))
            .where(
                InventoryBatch.product_id == p.id,
                InventoryBatch.business_id == user.business_id,
            )
        )
        qty = inv_q.scalar() or 0
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
    result = await db.execute(
        select(Product).where(
            Product.barcode == barcode,
            Product.business_id == user.business_id,
        )
    )
    product = result.scalar_one_or_none()
    if product:
        return BarcodeLookupResponse(found=True, product=ProductResponse.model_validate(product))
    return BarcodeLookupResponse(found=False)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    req: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:create")),
):
    product = Product(
        business_id=user.business_id,
        name=req.name,
        name_sw=req.name_sw,
        barcode=req.barcode,
        category=req.category,
        unit=req.unit,
        price=req.price,
        cost_price=req.cost_price,
        tax_rate=req.tax_rate,
    )
    db.add(product)
    await db.flush()
    
    # Create initial inventory batch
    if req.quantity > 0:
        batch = InventoryBatch(
            business_id=user.business_id,
            branch_id="",  # Will be set when branch system is complete
            product_id=product.id,
            quantity=req.quantity,
            min_quantity=req.min_quantity,
        )
        db.add(batch)
    
    await db.flush()
    return ProductResponse.model_validate(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.business_id == user.business_id,
        )
    )
    product = result.scalar_one_or_none()
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
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.business_id == user.business_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise NotFoundError("Product not found")
    
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    
    await db.flush()
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("product:delete")),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.business_id == user.business_id,
        )
    )
    product = result.scalar_one_or_none()
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
    result = await db.execute(
        select(Product).where(
            Product.id == req.product_id,
            Product.business_id == user.business_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise NotFoundError("Product not found")
    
    # Find or create inventory batch
    batch_result = await db.execute(
        select(InventoryBatch).where(
            InventoryBatch.product_id == req.product_id,
            InventoryBatch.business_id == user.business_id,
        ).limit(1)
    )
    batch = batch_result.scalar_one_or_none()
    if batch:
        batch.quantity += req.quantity
    else:
        batch = InventoryBatch(
            business_id=user.business_id,
            branch_id="",
            product_id=product.id,
            quantity=max(0, req.quantity),
        )
        db.add(batch)
    
    await db.flush()
    return ProductResponse.model_validate(product)


@router.get("/categories/list")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product.category, func.count(Product.id))
        .where(
            Product.business_id == user.business_id,
            Product.is_active == True,
            Product.category.isnot(None),
        )
        .group_by(Product.category)
        .order_by(Product.category)
    )
    categories = [{"name": row[0], "count": row[1]} for row in result.all()]
    return {"categories": categories}
