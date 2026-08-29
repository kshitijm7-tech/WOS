"""
Pydantic schemas for Part 2.1 AI foundation — offline MockRocketRideClient only.
All enums and bounds are validated here, not just in the DB.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class AIAnalysisStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AIRecommendation(str, Enum):
    REPAIR = "REPAIR"
    REPLACE = "REPLACE"
    DENY = "DENY"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AIValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


class AIStageOutput(BaseModel):
    stage: str
    result: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class AIDecisionOut(BaseModel):
    id: int
    claim_id: int
    recommendation: AIRecommendation
    confidence: float = Field(..., ge=0, le=0.97)
    evidence: List[str] = []
    risk_flags: List[str] = []
    missing_information: List[str] = []
    requires_human_review: bool
    review_reason: Optional[str] = None
    final_outcome: Optional[str] = None
    model: Optional[str] = None
    validation_status: Optional[AIValidationStatus] = None
    validation_errors: Optional[List[Dict[str, Any]]] = None
    decision_version: Optional[int] = None
    decision_score: Optional[float] = Field(None, ge=0, le=1)
    confidence_band: Optional[str] = None
    conflicts: Optional[List[Dict[str, Any]]] = None
    explanation: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        if v < 0 or v > 0.97:
            raise ValueError("confidence must be between 0 and 0.97")
        return v


class AIAnalysisResponse(BaseModel):
    claim_id: int
    claim_code: str
    ai_analysis_status: AIAnalysisStatus
    ai_analysis_requested_at: Optional[datetime] = None
    ai_analysis_completed_at: Optional[datetime] = None
    ai_analysis_error: Optional[str] = None
    stages: List[AIStageOutput] = []
    decision: Optional[AIDecisionOut] = None
    # For backwards compat, expose top-level fields if decision exists
    recommendation: Optional[AIRecommendation] = None
    confidence: Optional[float] = None
    validation_status: Optional[AIValidationStatus] = None
    requires_human_review: Optional[bool] = None


class AIAnalyzeRequest(BaseModel):
    # No body needed for now; placeholder for future force flag
    force: bool = Field(False, description="Force re-analysis even if COMPLETED")


class AIAnalyzeStartResponse(BaseModel):
    claim_id: int
    status: AIAnalysisStatus
    message: str
