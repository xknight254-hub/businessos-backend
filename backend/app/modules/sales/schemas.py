from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class SaleItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=1)


class SaleCreate(BaseModel):
    items: List[SaleItemCreate] = Field(..., min_length=1)
    payment_method: str = "mpesa"
    customer_id: Optional[str] = None
    discount: int = 0
    notes: Optional[str] = None


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: int
    total: int


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    amount: int
    method: str
    reference: Optional[str] = None
    status: str


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    total: int
    discount: int
    status: str
    payment_method: Optional[str]
    items: List[SaleItemResponse] = []
    payments: List[PaymentResponse] = []
    customer_id: Optional[str] = None
    created_at: datetime


class SaleListResponse(BaseModel):
    items: List[SaleResponse]
    total: int
    page: int
    per_page: int
    summary: Optional[dict] = None


class DailySummaryResponse(BaseModel):
    date: str
    total_sales: int
    total_revenue: int
    total_cash: int
    total_mpesa: int
    total_discount: int
    transaction_count: int
    top_products: List[dict] = []
