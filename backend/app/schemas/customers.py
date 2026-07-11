from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    credit_limit: Optional[int] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    credit_limit: Optional[int] = None
    notes: Optional[str] = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    credit_limit: int = 0
    credit_balance: int = 0
    total_visits: int = 0
    total_spent: int = 0
    last_visit: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime


class CustomerListResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    per_page: int
