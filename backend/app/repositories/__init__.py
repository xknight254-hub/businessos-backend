"""Per-domain repositories (M3.2).

Each repository encapsulates all DB access for its domain. Routers and
services depend on repositories, never on the raw session — this enforces
the blueprint coding standard: "repositories only access DB."
"""
from app.repositories.products import ProductRepository
from app.repositories.customers import CustomerRepository
from app.repositories.sales import SaleRepository
from app.repositories.payments import PaymentRepository

__all__ = [
    "ProductRepository",
    "CustomerRepository",
    "SaleRepository",
    "PaymentRepository",
]
