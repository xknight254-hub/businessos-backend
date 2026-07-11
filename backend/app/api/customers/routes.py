from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError
from app.core.rbac import require_permission
from app.models import User
from app.schemas.customers import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
)
from app.api.auth.dependencies import get_current_user
from app.repositories import CustomerRepository

router = APIRouter(prefix="/customers", tags=["Customers"])


def _repo(db: AsyncSession, user: User) -> CustomerRepository:
    return CustomerRepository(db, user.business_id)


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customers, total = await _repo(db, user).list(page=page, per_page=per_page, search=search)
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
    repo = _repo(db, user)
    if req.phone:
        if await repo.get_by_phone(req.phone):
            raise ConflictError("Customer with this phone already exists")
    customer = await repo.create(
        name=req.name, phone=req.phone, email=req.email,
        credit_limit=req.credit_limit or 0, notes=req.notes,
    )
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    customer = await _repo(db, user).get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    req: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:update")),
):
    repo = _repo(db, user)
    customer = await repo.get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/add")
async def add_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:credit")),
):
    customer = await _repo(db, user).get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    if customer.credit_balance + amount > (customer.credit_limit or 0):
        raise BadRequestError("Credit limit exceeded")
    customer.credit_balance = (customer.credit_balance or 0) + amount
    await db.flush()
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/credit/pay")
async def pay_credit(
    customer_id: str,
    amount: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("customer:credit")),
):
    customer = await _repo(db, user).get(customer_id)
    if not customer:
        raise NotFoundError("Customer not found")
    customer.credit_balance = max(0, (customer.credit_balance or 0) - amount)
    await db.flush()
    return CustomerResponse.model_validate(customer)
