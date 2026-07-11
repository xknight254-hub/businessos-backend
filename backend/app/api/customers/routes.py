from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.core.database import get_db
from app.models import Customer, User
from app.schemas.customers import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
)
from app.api.auth.dependencies import get_current_user
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Customer).where(Customer.business_id == user.business_id)
    
    if search:
        query = query.where(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.phone.ilike(f"%{search}%"),
            )
        )
    
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    
    result = await db.execute(
        query.order_by(Customer.name).offset((page - 1) * per_page).limit(per_page)
    )
    customers = result.scalars().all()
    
    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total, page=page, per_page=per_page,
    )


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    req: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Check for duplicate phone
    if req.phone:
        result = await db.execute(
            select(Customer).where(
                Customer.phone == req.phone,
                Customer.business_id == user.business_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Customer with this phone already exists")
    
    customer = Customer(
        business_id=user.business_id,
        name=req.name,
        phone=req.phone,
        email=req.email,
        credit_limit=req.credit_limit or 0,
        notes=req.notes,
    )
    db.add(customer)
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.business_id == user.business_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    req: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.business_id == user.business_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)
    
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/add")
async def add_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.business_id == user.business_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    if customer.credit_balance + amount > (customer.credit_limit or 0):
        raise HTTPException(status_code=400, detail="Credit limit exceeded")
    
    customer.credit_balance = (customer.credit_balance or 0) + amount
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/pay")
async def pay_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.business_id == user.business_id,
        )
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer.credit_balance = max(0, (customer.credit_balance or 0) - amount)
    await db.flush()
    return CustomerResponse.model_validate(customer)
