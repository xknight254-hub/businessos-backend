from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class ProductCreate(BaseModel):
    name: str
    name_sw: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    unit: str = "pcs"
    price: int  # in KES cents
    cost_price: Optional[int] = None
    tax_rate: str = "B"
    quantity: int = 0
    min_quantity: int = 0


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    name_sw: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[int] = None
    cost_price: Optional[int] = None
    tax_rate: Optional[str] = None
    min_quantity: Optional[int] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: str
    name: str
    name_sw: Optional[str] = None
    barcode: Optional[str] = None
    category: Optional[str] = None
    unit: str
    price: int
    cost_price: Optional[int] = None
    tax_rate: str
    quantity: int = 0
    min_quantity: int = 0
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
    id: str

class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    per_page: int


class BarcodeLookupResponse(BaseModel):
    found: bool
    product: Optional[ProductResponse] = None


class StockAdjustment(BaseModel):
    product_id: str
    quantity: int  # positive = add, negative = remove
    reason: str  # received, sold, spoiled, expired, adjustment
