from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Numeric, Text, JSON, Index
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True)
    claim_code = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    serial_id = Column(Integer, ForeignKey("product_serials.id"))
    retailer_id = Column(Integer, ForeignKey("retailers.id"))
    fault_description = Column(Text, nullable=False)
    fault_category = Column(String(100))
    status = Column(String(40), nullable=False, default="SUBMITTED")
    # Snapshot of purchase date at claim time (denormalized from ProductSerial for audit)
    purchase_date = Column(Date, nullable=True)
    # Deterministic warranty verification result (Phase 1.2, no AI)
    warranty_eligible = Column(Boolean, nullable=True)
    eligibility_reason = Column(Text, nullable=True)
    warranty_checked_at = Column(DateTime(timezone=True), nullable=True)
    # Exclusions triggered (array of strings) — stored as JSON for SQLite compat
    exclusions_triggered = Column(ARRAY(String).with_variant(JSON(), "sqlite"), nullable=True)
    missing_information = Column(ARRAY(String).with_variant(JSON(), "sqlite"), nullable=True)
    final_decision = Column(String(30))
    confidence = Column(Numeric(5, 2))
    is_high_value = Column(Boolean, default=False)
    # Part 2.1: AI analysis lifecycle (offline, MockRocketRideClient)
    ai_analysis_status = Column(String(30), nullable=True, default="PENDING")
    ai_analysis_requested_at = Column(DateTime(timezone=True), nullable=True)
    ai_analysis_completed_at = Column(DateTime(timezone=True), nullable=True)
    ai_analysis_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer = relationship("Customer")
    product = relationship("Product")
    serial = relationship("ProductSerial")
    retailer = relationship("Retailer")


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    evidence_type = Column(String(30), nullable=False)  # INVOICE | PHOTO | VIDEO | OTHER
    file_path = Column(String(500), nullable=False)
    # Secure file handling (Part 1.2)
    original_filename = Column(String(255), nullable=True)
    stored_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    description = Column(Text, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    claim = relationship("Claim")
    uploaded_by = relationship("User")


class ClaimAnalysis(Base):
    __tablename__ = "claim_analysis"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    stage = Column(String(50), nullable=False)
    result = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_claim_analysis_claim_stage", "claim_id", "stage"),
    )


class ClaimDecision(Base):
    __tablename__ = "claim_decisions"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    recommendation = Column(String(30), nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    evidence = Column(ARRAY(String).with_variant(JSON(), "sqlite"))
    risk_flags = Column(ARRAY(String).with_variant(JSON(), "sqlite"))
    missing_information = Column(ARRAY(String).with_variant(JSON(), "sqlite"))
    requires_human_review = Column(Boolean, default=False)
    review_reason = Column(String(255))
    final_outcome = Column(String(30))
    # Part 2.1: AI persistence
    model = Column(String(100), nullable=True)
    validation_status = Column(String(30), nullable=True)
    validation_errors = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    # Part 2.3: Governance
    decision_version = Column(Integer, nullable=False, default=1)
    decision_score = Column(Numeric(5, 2), nullable=True)
    confidence_band = Column(String(20), nullable=True)  # HIGH|MEDIUM|LOW
    conflicts = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)  # List[Conflict]
    explanation = Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)  # DecisionExplanation
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ClaimReview(Base):
    __tablename__ = "claim_reviews"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    reviewed_by_admin_id = Column(Integer, ForeignKey("admins.id"))
    claim_decision_id = Column(Integer, ForeignKey("claim_decisions.id"), nullable=True)
    action = Column(String(30), nullable=False)
    notes = Column(Text)
    # Part 2.3: Review governance
    status = Column(String(30), nullable=True, default="PENDING")  # PENDING|IN_PROGRESS|COMPLETED|REQUESTED_INFORMATION|OVERRIDDEN
    human_decision = Column(String(30), nullable=True)  # APPROVE|REJECT|REQUEST_INFO|OVERRIDE|REPLACE etc.
    override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClaimTimeline(Base):
    __tablename__ = "claim_timeline"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(100))
    notes = Column(Text)
    # Structured metadata for audit trail (e.g., old_status->new_status, warranty result)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    claim = relationship("Claim")


class AIExecution(Base):
    __tablename__ = "ai_executions"
    id = Column(Integer, primary_key=True)
    execution_id = Column(String(64), unique=True, nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)  # QUEUED|RUNNING|VALIDATING|GOVERNING|COMPLETED|FAILED|CANCELLED|TIMED_OUT
    provider = Column(String(50), nullable=False, default="mock")
    model = Column(String(100), nullable=False, default="mock-v1")
    pipeline_version = Column(String(20), nullable=False, default="2.4")
    attempt = Column(Integer, nullable=False, default=1)
    requested_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_ai_executions_claim_status", "claim_id", "status"),
        Index("idx_ai_executions_execution_id", "execution_id"),
    )
