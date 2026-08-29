from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HistoricalCase(Base):
    __tablename__ = "historical_cases"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    fault_category = Column(String(100))
    resolution = Column(String(30))
    summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FaultEvent(Base):
    __tablename__ = "fault_events"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("production_batches.id"))
    component = Column(String(100), nullable=False)
    claim_id = Column(Integer, ForeignKey("claims.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RiskFlag(Base):
    __tablename__ = "risk_flags"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    flag_type = Column(String(100), nullable=False)
    detail = Column(Text)
    weight = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    actor = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    entity = Column(String(100))
    entity_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
