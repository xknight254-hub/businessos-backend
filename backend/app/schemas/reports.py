from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RevenueSummaryResponse(BaseModel):
    today: int
    yesterday: int
    this_week: int
    last_week: int
    this_month: int
    last_month: int
    daily_average: int
    trend: str  # up, down, flat
    trend_percent: float


class ProductPerformanceItem(BaseModel):
    product_id: str
    product_name: str
    quantity_sold: int
    revenue: int
    profit: int
    margin_percent: float
    stock_remaining: int


class CustomerLifetimeItem(BaseModel):
    customer_id: str
    name: str
    phone: Optional[str]
    total_visits: int
    total_spent: int
    avg_spent_per_visit: int
    credit_balance: int
    last_visit: Optional[datetime]


class ExpenseSummaryResponse(BaseModel):
    total_expenses: int
    by_category: List[dict]
    top_expenses: List[dict]


class ProfitLossResponse(BaseModel):
    date_from: str
    date_to: str
    total_revenue: int
    total_cost_of_goods: int
    gross_profit: int
    gross_margin: float
    total_expenses: int
    net_profit: int
    net_margin: float
    revenue_breakdown: dict
    expense_breakdown: dict


class DailySalesChartItem(BaseModel):
    date: str
    revenue: int
    transactions: int
    cash: int
    mpesa: int


class AnalyticsDashboardResponse(BaseModel):
    revenue: RevenueSummaryResponse
    top_products: List[ProductPerformanceItem]
    top_customers: List[CustomerLifetimeItem]
    sales_chart: List[DailySalesChartItem]
    low_stock_count: int
    overdue_credit_total: int
    recent_alerts: List[dict]
