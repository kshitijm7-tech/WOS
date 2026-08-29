from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, JSON, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Retailer(Base):
    __tablename__ = "retailers"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    region = Column(String(100))
    trust_score = Column(Numeric(4, 1), default=100.0)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), unique=True, nullable=False)
    category = Column(String(100), nullable=False)
    manufacturer = Column(String(255))
    warranty_period_months = Column(Integer, nullable=False, default=12)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProductionBatch(Base):
    __tablename__ = "production_batches"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_code = Column(String(100), nullable=False)
    produced_on = Column(Date)
    units_produced = Column(Integer, default=0)

    product = relationship("Product")

    __table_args__ = (UniqueConstraint("product_id", "batch_code", name="uq_batch_product_code"),)


class ProductSerial(Base):
    __tablename__ = "product_serials"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("production_batches.id"))
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    sold_by_retailer_id = Column(Integer, ForeignKey("retailers.id"))
    purchase_date = Column(Date)
    owner_customer_id = Column(Integer, ForeignKey("customers.id"))

    product = relationship("Product")
    batch = relationship("ProductionBatch")


class WarrantyPolicy(Base):
    __tablename__ = "warranty_policies"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warranty_months = Column(Integer, nullable=False)
    # TEXT[] in PostgreSQL, JSON fallback for SQLite (preserves array semantics)
    covered = Column(ARRAY(String).with_variant(JSON(), "sqlite"))
    not_covered = Column(ARRAY(String).with_variant(JSON(), "sqlite"))
    # Human-readable conditions and covered fault categories for deterministic rules
    conditions = Column(Text, nullable=True)
    covered_fault_categories = Column(ARRAY(String).with_variant(JSON(), "sqlite"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")
