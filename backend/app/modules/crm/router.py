from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError
from app.core.rbac import require_permission
from app.models import User, Customer
from app.modules.crm.schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
)
from app.modules.crm.repository import CustomerRepository
from app.modules.crm.events import CUSTOMER_CREATED
from app.core.events import event_bus, Event
from app.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = CustomerRepository(db, user.business_id)
    customers, total = await repo.list(page=page, per_page=per_page, search=search)
    return CustomerListResponse(
        items=[CustomerResponse.model_validate(c) for c in customers],
        total=total, page=page, per_page=per_page,
    )


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    req: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:create")),
):
    repo = CustomerRepository(db, user.business_id)
    customer = await repo.create(
        name=req.name, phone=req.phone, email=req.email,
        credit_limit=req.credit_limit or 0, notes=req.notes,
    )
    await db.flush()
    await event_bus.publish(Event(
        type=CUSTOMER_CREATED,
        business_id=user.business_id,
        payload={"customer_id": customer.id, "name": customer.name, "phone": customer.phone},
    ))
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = CustomerRepository(db, user.business_id)
    customer = await repo.get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    req: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:update")),
):
    repo = CustomerRepository(db, user.business_id)
    customer = await repo.get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    update_fields = req.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if field == "credit_limit":
            field = "credit_limit"
        setattr(customer, field, value)
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/add", response_model=CustomerResponse)
async def add_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:credit")),
):
    repo = CustomerRepository(db, user.business_id)
    customer = await repo.get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    await repo.adjust_credit(customer, amount)
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/pay", response_model=CustomerResponse)
async def pay_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:credit")),
):
    repo = CustomerRepository(db, user.business_id)
    customer = await repo.get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    if amount > customer.credit_balance:
        raise BadRequestError("Payment exceeds credit balance")
    await repo.pay_credit(customer, amount)
    return CustomerResponse.model_validate(customer)
