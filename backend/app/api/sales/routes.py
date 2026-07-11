from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.database import get_db
from app.core.exceptions import NotFoundError, BadRequestError
from app.core.rbac import require_permission
from app.models import User, Sale, SaleItem, Payment, Product, InventoryBatch, Customer
from app.schemas.sales import (
    SaleCreate, SaleResponse, SaleListResponse, SaleItemResponse,
    PaymentResponse, DailySummaryResponse,
)
from app.api.auth.dependencies import get_current_user
from app.repositories import SaleRepository

router = APIRouter(prefix="/sales", tags=["Sales"])


def _repo(db: AsyncSession, user: User) -> SaleRepository:
    return SaleRepository(db, user.business_id)


async def _sale_to_response(sale: Sale, db: AsyncSession, user: User) -> SaleResponse:
    repo = _repo(db, user)
    items = []
    for si, pname in await repo.get_items(sale.id):
        items.append(SaleItemResponse(
            id=si.id, product_id=si.product_id, product_name=pname,
            quantity=si.quantity, unit_price=si.unit_price, total=si.total,
        ))
    payments = [PaymentResponse.model_validate(p) for p in await repo.get_payments(sale.id)]
    return SaleResponse(
        id=sale.id, total=sale.total, discount=sale.discount, status=sale.status,
        payment_method=sale.payment_method, items=items, payments=payments,
        customer_id=sale.customer_id, created_at=sale.created_at,
    )


@router.post("", response_model=SaleResponse, status_code=201)
async def create_sale(
    req: SaleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("sale:create")),
):
    repo = _repo(db, user)
    total = 0
    sale_items_data = []
    for item in req.items:
        product = await repo.get_product(item.product_id)
        if not product:
            raise NotFoundError(f"Product {item.product_id} not found")
        item_total = product.price * item.quantity
        total += item_total
        sale_items_data.append({"product": product, "quantity": item.quantity,
                               "unit_price": product.price, "total": item_total})
    total -= req.discount

    sale = await repo.create_sale(
        branch_id="", user_id=user.id, customer_id=req.customer_id,
        total=total, discount=req.discount, payment_method=req.payment_method,
        notes=req.notes,
    )
    for sd in sale_items_data:
        await repo.create_sale_item(
            sale_id=sale.id, product_id=sd["product"].id,
            quantity=sd["quantity"], unit_price=sd["unit_price"], total=sd["total"],
        )
        batch = await repo.get_inventory_batch(sd["product"].id)
        if batch:
            batch.quantity -= sd["quantity"]

    await repo.create_payment(sale_id=sale.id, amount=total, method=req.payment_method)

    if req.customer_id:
        customer = await repo.get_customer(req.customer_id)
        if customer:
            customer.total_visits = (customer.total_visits or 0) + 1
            customer.total_spent = (customer.total_spent or 0) + total
            customer.last_visit = datetime.now(timezone.utc)

    await db.flush()
    return await _sale_to_response(sale, db, user)


@router.get("", response_model=SaleListResponse)
async def list_sales(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    df = datetime.fromisoformat(date_from) if date_from else None
    dt = datetime.fromisoformat(date_to) + timedelta(days=1) if date_to else None
    repo = _repo(db, user)
    sales, total = await repo.list(page=page, per_page=per_page, date_from=df, date_to=dt)
    items = [await _sale_to_response(s, db, user) for s in sales]
    return SaleListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/summary/daily", response_model=DailySummaryResponse)
async def daily_summary(
    date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = _repo(db, user)
    query_date = datetime.fromisoformat(date) if date else datetime.now(timezone.utc)
    day_start = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    sales = await repo.list_by_day(day_start, day_end)
    total_revenue = sum(s.total for s in sales)
    total_discount = sum(s.discount for s in sales)
    total_cash = sum(s.total for s in sales if s.payment_method == "cash")
    total_mpesa = sum(s.total for s in sales if s.payment_method == "mpesa")
    top_products = await repo.top_products(day_start, day_end)
    return DailySummaryResponse(
        date=query_date.strftime("%Y-%m-%d"),
        total_sales=len(sales), total_revenue=total_revenue,
        total_cash=total_cash, total_mpesa=total_mpesa,
        total_discount=total_discount, transaction_count=len(sales),
        top_products=top_products,
    )


@router.get("/{sale_id}", response_model=SaleResponse)
async def get_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sale = await _repo(db, user).get(sale_id)
    if not sale:
        raise NotFoundError("Sale not found")
    return await _sale_to_response(sale, db, user)


@router.post("/{sale_id}/void", response_model=SaleResponse)
async def void_sale(
    sale_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("sale:void")),
):
    repo = _repo(db, user)
    sale = await repo.get(sale_id)
    if not sale:
        raise NotFoundError("Sale not found")
    if sale.status != "completed":
        raise BadRequestError("Sale already voided")
    sale.status = "voided"
    for si in (await repo.get_items(sale_id)):
        batch = await repo.get_inventory_batch(si[0].product_id)
        if batch:
            batch.quantity += si[0].quantity
    await db.flush()
    return await _sale_to_response(sale, db, user)
