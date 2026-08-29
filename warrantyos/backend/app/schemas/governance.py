"""
Governance schemas — Part 2.3
Confidence bands, conflicts, explanation, scorecard, review workflow.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum

# Confidence bands (configurable thresholds)
class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

# Decision states for governance
class DecisionGovernanceStatus(str, Enum):
    AI_SUGGESTION = "AI_SUGGESTION"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"
    OVERRIDDEN = "OVERRIDDEN"

class ConflictSeverity(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Conflict(BaseModel):
    conflict_code: str  # e.g., WARRANTY_CONFLICT, SERIAL_MISMATCH
    description: str
    source: str  # warranty | serial | evidence | policy
    severity: ConflictSeverity
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DecisionExplanation(BaseModel):
    summary: str
    reasoning_factors: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    historical_case_references: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    confidence_explanation: str = ""

class Scorecard(BaseModel):
    evidence_completeness: float = Field(ge=0, le=1)
    warranty_consistency: float = Field(ge=0, le=1)
    policy_alignment: float = Field(ge=0, le=1)
    historical_similarity: float = Field(ge=0, le=1)
    risk_profile: float = Field(ge=0, le=1)
    claim_consistency: float = Field(ge=0, le=1)
    overall_decision_score: float = Field(ge=0, le=1)

class DecisionGovernanceResult(BaseModel):
    recommendation: str
    confidence: float
    confidence_band: ConfidenceBand
    decision_score: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    evidence_completeness: str  # COMPLETE/PARTIAL/INCOMPLETE
    requires_human_review: bool
    review_reasons: List[str] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    explanation: DecisionExplanation
    scorecard: Scorecard
    validation_status: str
    # Governance status
    governance_status: DecisionGovernanceStatus

class ReviewStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REQUESTED_INFORMATION = "REQUESTED_INFORMATION"
    OVERRIDDEN = "OVERRIDDEN"

class ReviewRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "REQUEST_INFORMATION", "OVERRIDE", "ESCALATE", "START_REVIEW"]
    decision: Optional[str] = Field(None, description="Required for OVERRIDE: new decision REPAIR/REPLACE/DENY etc.")
    reason: Optional[str] = Field(None, description="Required for OVERRIDE and REJECT")
    notes: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    claim_id: int
    claim_decision_id: Optional[int] = None
    reviewed_by_admin_id: Optional[int] = None
    action: str
    notes: Optional[str] = None
    status: Optional[str] = None
    human_decision: Optional[str] = None
    override: bool = False
    override_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
