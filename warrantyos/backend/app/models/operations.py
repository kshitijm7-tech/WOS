from sqlalchemy import Column, Integer, String, ForeignKey, Date

from app.core.database import Base


class RepairOrder(Base):
    __tablename__ = "repair_orders"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), unique=True, nullable=False)
    scheduled_date = Column(Date)
    technician = Column(String(255))
    status = Column(String(30), default="SCHEDULED")


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse = Column(String(100), nullable=False)
    available_qty = Column(Integer, default=0)
    reserved_qty = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=10)


class ReplacementOrder(Base):
    __tablename__ = "replacement_orders"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), unique=True, nullable=False)
    inventory_id = Column(Integer, ForeignKey("inventory.id"))
    status = Column(String(30), default="PROCESSING")
