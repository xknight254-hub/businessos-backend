from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    # Naive UTC. SQLAlchemy DateTime columns are tz-naive; storing aware
    # datetimes works on SQLite but breaks arithmetic/comparison on
    # Postgres (asyncpg). Naive UTC is consistent across both engines.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------- Business / Organization ----------

class Business(Base):
    __tablename__ = "businesses"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # restaurant, shop, salon, butchery, pharmacy, general
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    currency = Column(String(3), default="KES")
    timezone = Column(String(50), default="Africa/Nairobi")
    is_active = Column(Boolean, default=True)
    settings = Column(Text, nullable=True)  # JSONB via Text for simplicity
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    branches = relationship("Branch", back_populates="business", cascade="all, delete-orphan")
    users = relationship("User", back_populates="business", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="business", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    suppliers = relationship("Supplier", back_populates="business", cascade="all, delete-orphan")


class Branch(Base):
    __tablename__ = "branches"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    location = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    business = relationship("Business", back_populates="branches")
    sales = relationship("Sale", back_populates="branch")
    inventory_batches = relationship("InventoryBatch", back_populates="branch")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    pin_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="staff")  # owner, manager, staff
    is_active = Column(Boolean, default=True)
    biometric_enabled = Column(Boolean, default=False)
    device_id = Column(String(255), nullable=True)
    fcm_token = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    business = relationship("Business", back_populates="users")


# ---------- Products & Inventory ----------

class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    name_sw = Column(String(255), nullable=True)
    barcode = Column(String(50), nullable=True, index=True)
    category = Column(String(100), nullable=True)
    unit = Column(String(20), default="pcs")  # pcs, kg, l, packet
    price = Column(Integer, nullable=False)  # in cents (KES)
    cost_price = Column(Integer, nullable=True)
    tax_rate = Column(String(1), default="B")  # A=0%, B=16%, C=0%, D=0%, E=8%
    image_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    business = relationship("Business", back_populates="products")
    sale_items = relationship("SaleItem", back_populates="product")
    inventory_batches = relationship("InventoryBatch", back_populates="product")


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(String, ForeignKey("branches.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=0)
    min_quantity = Column(Integer, default=0)
    expiry_date = Column(DateTime, nullable=True)
    batch_number = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    product = relationship("Product", back_populates="inventory_batches")
    branch = relationship("Branch", back_populates="inventory_batches")


# ---------- Sales ----------

class Sale(Base):
    __tablename__ = "sales"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    branch_id = Column(String, ForeignKey("branches.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    total = Column(Integer, nullable=False)  # in cents
    discount = Column(Integer, default=0)
    status = Column(String(20), default="completed")  # completed, voided, refunded
    payment_method = Column(String(20), nullable=True)  # mpesa, cash, mixed
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    branch = relationship("Branch", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="sale", cascade="all, delete-orphan")
    customer = relationship("Customer", back_populates="sales")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    sale_id = Column(String, ForeignKey("sales.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=generate_uuid)
    sale_id = Column(String, ForeignKey("sales.id"), nullable=True)
    amount = Column(Integer, nullable=False)
    method = Column(String(20), nullable=False)  # mpesa, cash
    reference = Column(String(100), nullable=True, index=True)  # M-Pesa receipt
    status = Column(String(20), default="completed")  # pending, completed, failed
    created_at = Column(DateTime, default=utcnow)

    sale = relationship("Sale", back_populates="payments")


# ---------- Customers ----------

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    credit_limit = Column(Integer, default=0)
    credit_balance = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    total_visits = Column(Integer, default=0)
    total_spent = Column(Integer, default=0)
    last_visit = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    business = relationship("Business", back_populates="customers")
    sales = relationship("Sale", back_populates="customer")


# ---------- Suppliers ----------

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    products = Column(Text, nullable=True)  # JSON array of product ids
    payment_terms = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    business = relationship("Business", back_populates="suppliers")


# ---------- M-Pesa Transactions ----------

class MpesaTransaction(Base):
    __tablename__ = "mpesa_transactions"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    phone = Column(String(20), nullable=True)
    reference = Column(String(100), index=True)
    transaction_type = Column(String(20))  # receive, send, reversal
    status = Column(String(20), default="pending")
    matched_sale_id = Column(String, ForeignKey("sales.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)


# ---------- Sync & Audit ----------

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    device_id = Column(String(255), nullable=True)
    action = Column(String(50))  # push, pull, conflict
    status = Column(String(20), default="completed")
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # create, update, delete, login, payment
    resource = Column(String(50), nullable=False)  # product, sale, customer, etc.
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class BusinessMemory(Base):
    """Business Memory store — RAG entries with embeddings."""
    __tablename__ = "business_memory"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    source = Column(String(50), default="observation")
    memory_type = Column(String(30), default="episodic")
    tags = Column(Text, nullable=True)
    confidence = Column(Integer, default=50)
    embedding = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AutomationRule(Base):
    """Automation rules — when condition triggers, execute action."""
    __tablename__ = "automation_rules"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    trigger_type = Column(String(50), nullable=False)
    condition_config = Column(Text, nullable=True)
    action_type = Column(String(50), nullable=False)
    action_config = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class AutomationLog(Base):
    """Log of automation rule executions."""
    __tablename__ = "automation_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    rule_id = Column(String, ForeignKey("automation_rules.id"), nullable=True)
    trigger_type = Column(String(50), nullable=False)
    action_type = Column(String(50), nullable=False)
    status = Column(String(20), default="pending")
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


# ---------- Notifications ----------

class Notification(Base):
    """In-app notifications produced by event-driven handlers (M4.3)."""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # low_stock, payment_received, customer_created
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    payload = Column(Text, nullable=True)  # JSON
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


# ---------- AI Prompts (M5.5) ----------

class Prompt(Base):
    """Versioned prompt templates, editable and tracked per business."""
    __tablename__ = "prompts"

    id = Column(String, primary_key=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False, index=True)
    key = Column(String(100), nullable=False)  # e.g. "sales_insight"
    version = Column(Integer, default=1, nullable=False)
    title = Column(String(255), nullable=False)
    template = Column(Text, nullable=False)  # supports {placeholders}
    model = Column(String(100), nullable=False, default="gpt-4o-mini")
    task = Column(String(50), nullable=False, default="insight")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        # one active prompt per key per business
        Index("ix_prompts_business_key_active", "business_id", "key", "is_active"),
    )
