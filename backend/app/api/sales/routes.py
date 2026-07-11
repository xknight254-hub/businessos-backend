from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from app.core.database import get_db
from app.models import (
    Sale, SaleItem, Payment, Product, InventoryBatch, Customer, Business,
)
from app.schemas.sales import (
    SaleCreate, SaleResponse, SaleListResponse, SaleItemResponse,
    PaymentResponse, DailySummaryResponse,
)
from app.api.auth.dependencies import get_current_user
from app.models import User
from datetime import datetime, timezone, timedelta
from typing import Optional

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("", response_model=SaleResponse, status_code=201)
async def create_sale(
    req: SaleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ("owner", "manager", "staff"):
        raise HTTPException(status_code=403, detail="Not authorized to make sales")
    
    # Calculate total from items
    total = 0
    sale_items_data = []
    
    for item in req.items:
        product_result = await db.execute(
            select(Product).where(
                Product.id == item.product_id,
                Product.business_id == user.business_id,
                Product.is_active == True,
            )
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        item_total = product.price * item.quantity
        total += item_total
        sale_items_data.append({
            "product": product,
            "quantity": item.quantity,
            "unit_price": product.price,
            "total": item_total,
        })
    
    total -= req.discount
    
    # Create sale
    sale = Sale(
        business_id=user.business_id,
        branch_id="",
        user_id=user.id,
        customer_id=req.customer_id,
        total=total,
        discount=req.discount,
        payment_method=req.payment_method,
        notes=req.notes,
    )
    db.add(sale)
    await db.flush()
    
    # Create sale items
    for sd in sale_items_data:
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=sd["product"].id,
            quantity=sd["quantity"],
            unit_price=sd["unit_price"],
            total=sd["total"],
        )
        db.add(sale_item)
        
        # Decrement inventory
        inv_result = await db.execute(
            select(InventoryBatch).where(
                InventoryBatch.product_id == sd["product"].id,
                InventoryBatch.business_id == user.business_id,
            ).limit(1)
        )
        batch = inv_result.scalar_one_or_none()
        if batch:
            batch.quantity -= sd["quantity"]
    
    # Create payment
    payment = Payment(
        sale_id=sale.id,
        amount=total,
        method=req.payment_method,
    )
    db.add(payment)
    
    # Update customer total
    if req.customer_id:
        cust_result = await db.execute(
            select(Customer).where(Customer.id == req.customer_id)
        )
        customer = cust_result.scalar_one_or_none()
        if customer:
            customer.total_visits = (customer.total_visits or 0) + 1
            customer.total_spent = (customer.total_spent or 0) + total
            customer.last_visit = datetime.now(timezone.utc)
    
    await db.flush()
    return await _sale_to_response(sale, db)


async def _sale_to_response(sale: Sale, db: AsyncSession) -> SaleResponse:
    # Get items
    items_result = await db.execute(
        select(SaleItem, Product.name).join(Product, SaleItem.product_id == Product.id)
        .where(SaleItem.sale_id == sale.id)
    )
    items = []
    for si, pname in items_result.all():
        items.append(SaleItemResponse(
            id=si.id,
            product_id=si.product_id,
            product_name=pname,
            quantity=si.quantity,
            unit_price=si.unit_price,
            total=si.total,
        ))
    
    # Get payments
    payments_result = await db.execute(
        select(Payment).where(Payment.sale_id == sale.id)
    )
    payments = [
        PaymentResponse.model_validate(p) for p in payments_result.scalars().all()
    ]
    
    return SaleResponse(
        id=sale.id,
        total=sale.total,
        discount=sale.discount,
        status=sale.status,
        payment_method=sale.payment_method,
        items=items,
        payments=payments,
        customer_id=sale.customer_id,
        created_at=sale.created_at,
    )


@router.get("", response_model=SaleListResponse)
async def list_sales(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Sale).where(Sale.business_id == user.business_id)
    
    if date_from:
        query = query.where(Sale.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(Sale.created_at <= datetime.fromisoformat(date_to) + timedelta(days=1))
    
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    
    result = await db.execute(
        query.order_by(desc(Sale.created_at))
        .offset((page - 1) * per_page).limit(per_page)
    )
    sales = result.scalars().all()
    
    items = []
    for sale in sales:
        items.append(await _sale_to_response(sale, db))
    
    return SaleListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/summary/daily", response_model=DailySummaryResponse)
async def daily_summary(
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query_date = datetime.fromisoformat(date) if date else datetime.now(timezone.utc)
    day_start = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    sales_query = select(Sale).where(
        Sale.business_id == user.business_id,
        Sale.created_at >= day_start,
        Sale.created_at < day_end,
        Sale.status == "completed",
    )
    result = await db.execute(sales_query)
    sales = result.scalars().all()
    
    total_revenue = sum(s.total for s in sales)
    total_discount = sum(s.discount for s in sales)
    total_cash = sum(s.total for s in sales if s.payment_method == "cash")
    total_mpesa = sum(s.total for s in sales if s.payment_method == "mpesa")
    
    # Top products
    items_result = await db.execute(
        select(
            Product.name, func.sum(SaleItem.quantity).label("qty"),
            func.sum(SaleItem.total).label("rev")
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.business_id == user.business_id,
            Sale.created_at >= day_start,
            Sale.created_at < day_end,
        )
        .group_by(Product.name)
        .order_by(desc("rev"))
        .limit(5)
    )
    top_products = [
        {"name": row[0], "quantity": row[1], "revenue": row[2]}
        for row in items_result.all()
    ]
    
    return DailySummaryResponse(
        date=query_date.strftime("%Y-%m-%d"),
        total_sales=len(sales),
        total_revenue=total_revenue,
        total_cash=total_cash,
        total_mpesa=total_mpesa,
        total_discount=total_discount,
        transaction_count=len(sales),
        top_products=top_products,
    )


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Sale).where(
            Sale.id == sale_id,
            Sale.business_id == user.business_id,
        )
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return await _sale_to_response(sale, db)


@router.post("/{sale_id}/void", response_model=SaleResponse)
async def void_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ("owner", "manager"):
        raise HTTPException(status_code=403, detail="Only owner/manager can void sales")
    
    result = await db.execute(
        select(Sale).where(
            Sale.id == sale_id,
            Sale.business_id == user.business_id,
        )
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.status != "completed":
        raise HTTPException(status_code=400, detail="Sale already voided")
    
    sale.status = "voided"
    
    # Restore inventory
    items_result = await db.execute(
        select(SaleItem).where(SaleItem.sale_id == sale_id)
    )
    for si in items_result.scalars().all():
        inv_result = await db.execute(
            select(InventoryBatch).where(
                InventoryBatch.product_id == si.product_id,
                InventoryBatch.business_id == user.business_id,
            ).limit(1)
        )
        batch = inv_result.scalar_one_or_none()
        if batch:
            batch.quantity += si.quantity
    
    await db.flush()
    return await _sale_to_response(sale, db)
