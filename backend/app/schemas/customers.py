"""Backward-compat shim: real code moved to app.modules.crm.schemas."""
from app.modules.crm.schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
)

__all__ = ["CustomerCreate", "CustomerUpdate", "CustomerResponse", "CustomerListResponse"]
