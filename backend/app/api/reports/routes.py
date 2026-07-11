from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from app.core.database import get_db
from app.models import Sale, SaleItem, Payment, Product, InventoryBatch, Customer, User
from app.schemas.reports import *
from app.api.auth.dependencies import get_current_user
from datetime import datetime, timedelta, timezone
from typing import Optional

router = APIRouter(prefix="/reports", tags=["Reports"])


def _day_start(days_ago=0):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/revenue/summary", response_model=RevenueSummaryResponse)
async def revenue_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today_start = _day_start(0)
    yesterday_start = _day_start(1)
    week_start = _day_start(datetime.now().weekday())
    last_week_start = _day_start(datetime.now().weekday() + 7)
    month_start = _day_start(datetime.now().day - 1)
    last_month_start = _day_start(30)

    async def revenue_since(start):
        result = await db.execute(
            select(func.coalesce(func.sum(Sale.total), 0))
            .where(Sale.business_id == user.business_id, Sale.status == "completed",
                   Sale.created_at >= start)
        )
        return result.scalar() or 0

    today = await revenue_since(today_start)
    yesterday = await revenue_since(yesterday_start) - await revenue_since(today_start)
    this_week = await revenue_since(week_start)
    last_week = await revenue_since(last_week_start) - await revenue_since(week_start)
    this_month = await revenue_since(month_start)
    last_month = await revenue_since(last_month_start) - await revenue_since(month_start)

    daily_avg = this_week // max(datetime.now().weekday() + 1, 1)
    trend = "up" if yesterday > daily_avg else "down" if yesterday < daily_avg else "flat"
    trend_pct = ((yesterday - daily_avg) / max(daily_avg, 1)) * 100

    return RevenueSummaryResponse(
        today=today, yesterday=yesterday, this_week=this_week, last_week=last_week,
        this_month=this_month, last_month=last_month, daily_average=daily_avg,
        trend=trend, trend_percent=round(trend_pct, 1),
    )


@router.get("/products/top", response_model=List[ProductPerformanceItem])
async def top_products(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = _day_start(0) - timedelta(days=days)
    result = await db.execute(
        select(
            Product.id, Product.name, Product.cost_price,
            func.sum(SaleItem.quantity).label("qty"),
            func.sum(SaleItem.total).label("revenue"),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(
            Sale.business_id == user.business_id,
            Sale.created_at >= since,
            Sale.status == "completed",
        )
        .group_by(Product.id, Product.name, Product.cost_price)
        .order_by(desc("revenue"))
        .limit(limit)
    )
    items = []
    for row in result.all():
        inv = await db.execute(
            select(func.coalesce(func.sum(InventoryBatch.quantity), 0))
            .where(
                InventoryBatch.product_id == row.id,
                InventoryBatch.business_id == user.business_id,
            )
        )
        stock = inv.scalar() or 0
        revenue = row.revenue or 0
        qty = row.qty or 1
        cost = (row.cost_price or 0) * qty
        profit = revenue - cost
        margin = (profit / max(revenue, 1)) * 100
        items.append(ProductPerformanceItem(
            product_id=row.id, product_name=row.name,
            quantity_sold=qty, revenue=revenue, profit=profit,
            margin_percent=round(margin, 1), stock_remaining=stock,
        ))
    return items


@router.get("/customers/top", response_model=List[CustomerLifetimeItem])
async def top_customers(
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            Customer.id, Customer.name, Customer.phone,
            Customer.total_visits, Customer.total_spent,
            Customer.credit_balance, Customer.last_visit,
        )
        .where(Customer.business_id == user.business_id)
        .order_by(desc(Customer.total_spent))
        .limit(limit)
    )
    items = []
    for row in result.all():
        items.append(CustomerLifetimeItem(
            customer_id=row.id, name=row.name, phone=row.phone,
            total_visits=row.total_visits or 0, total_spent=row.total_spent or 0,
            avg_spent_per_visit=((row.total_spent or 0) // max(row.total_visits or 1, 1)),
            credit_balance=row.credit_balance or 0, last_visit=row.last_visit,
        ))
    return items


@router.get("/sales/chart", response_model=List[DailySalesChartItem])
async def sales_chart(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = _day_start(0) - timedelta(days=days - 1)
    result = await db.execute(
        select(
            func.date(Sale.created_at).label("date"),
            func.coalesce(func.sum(Sale.total), 0).label("revenue"),
            func.count(Sale.id).label("txns"),
            func.coalesce(func.sum(Sale.total).filter(Sale.payment_method == "cash"), 0).label("cash"),
            func.coalesce(func.sum(Sale.total).filter(Sale.payment_method == "mpesa"), 0).label("mpesa"),
        )
        .where(
            Sale.business_id == user.business_id,
            Sale.created_at >= since,
            Sale.status == "completed",
        )
        .group_by(func.date(Sale.created_at))
        .order_by("date")
    )
    return [
        DailySalesChartItem(
            date=str(row[0]), revenue=row[1], transactions=row[2],
            cash=row[3], mpesa=row[4],
        ) for row in result.all()
    ]


@router.get("/profit-loss", response_model=ProfitLossResponse)
async def profit_loss(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    start = datetime.fromisoformat(date_from) if date_from else _day_start(30)
    end = datetime.fromisoformat(date_to) if date_to else datetime.now(timezone.utc)

    rev_result = await db.execute(
        select(func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.business_id == user.business_id, Sale.status == "completed",
               Sale.created_at >= start, Sale.created_at <= end)
    )
    total_revenue = rev_result.scalar() or 0

    cogs_result = await db.execute(
        select(func.coalesce(func.sum(SaleItem.quantity * func.coalesce(Product.cost_price, 0)), 0))
        .join(Product, Product.id == SaleItem.product_id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.business_id == user.business_id, Sale.status == "completed",
               Sale.created_at >= start, Sale.created_at <= end)
    )
    cogs = cogs_result.scalar() or 0

    gross = total_revenue - cogs
    gross_margin = (gross / max(total_revenue, 1)) * 100

    # Payment method breakdown
    method_result = await db.execute(
        select(Sale.payment_method, func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.business_id == user.business_id, Sale.status == "completed",
               Sale.created_at >= start, Sale.created_at <= end)
        .group_by(Sale.payment_method)
    )
    revenue_breakdown = {row[0] or "unknown": row[1] for row in method_result.all()}

    return ProfitLossResponse(
        date_from=start.strftime("%Y-%m-%d"), date_to=end.strftime("%Y-%m-%d"),
        total_revenue=total_revenue, total_cost_of_goods=cogs,
        gross_profit=gross, gross_margin=round(gross_margin, 1),
        total_expenses=0, net_profit=gross, net_margin=round(gross_margin, 1),
        revenue_breakdown=revenue_breakdown, expense_breakdown={},
    )


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
async def analytics_dashboard_view(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rev = await revenue_summary(db, user)

    prods = await top_products(30, 5, db, user)
    custs = await top_customers(90, 5, db, user)
    chart = await sales_chart(30, db, user)

    low = await db.execute(
        select(func.count(Product.id))
        .join(InventoryBatch, InventoryBatch.product_id == Product.id)
        .where(
            Product.business_id == user.business_id,
            InventoryBatch.quantity < InventoryBatch.min_quantity,
            Product.is_active == True,
        )
    )
    low_stock = low.scalar() or 0

    credit = await db.execute(
        select(func.coalesce(func.sum(Customer.credit_balance), 0))
        .where(Customer.business_id == user.business_id)
    )
    overdue_credit = credit.scalar() or 0

    return AnalyticsDashboardResponse(
        revenue=rev, top_products=prods, top_customers=custs,
        sales_chart=chart, low_stock_count=low_stock,
        overdue_credit_total=overdue_credit, recent_alerts=[],
    )
