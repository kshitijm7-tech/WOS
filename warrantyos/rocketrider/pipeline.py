"""
RocketRide pipeline contract.

Defines the 7-stage claim-analysis workflow used across the app:

  CLAIM INPUT
    -> DOCUMENT_EXTRACTION
    -> POLICY_CHECK
    -> EVIDENCE_ANALYSIS
    -> SIMILAR_CASE_SEARCH
    -> DECISION_AGENT
    -> VALIDATOR
  -> (HUMAN REVIEW IF REQUIRED, decided by backend/app/services/claim_workflow.py)
  -> FINAL ACTION

This module only defines *data shapes* and the stage order — no vendor-specific code lives
here. See rocketrider/adapter.py for the client interface that actually runs these stages,
and rocketrider/README.md for where to plug in the real RocketRide SDK.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


STAGES: List[str] = [
    "DOCUMENT_EXTRACTION",
    "POLICY_CHECK",
    "EVIDENCE_ANALYSIS",
    "SIMILAR_CASE_SEARCH",
    "DECISION_AGENT",
    "VALIDATOR",
]


@dataclass
class ClaimPipelineInput:
    claim_code: str
    product_name: str
    category: str
    serial_number: str
    fault_description: str
    purchase_date: Optional[str]
    warranty_months: int
    covered: List[str]
    not_covered: List[str]
    has_invoice: bool
    has_photo: bool
    has_video: bool
    customer_claim_count_90d: int = 0


@dataclass
class ClaimPipelineResult:
    """Structured output every stage contributes to; this is what claim_analysis rows store."""
    stage_outputs: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = "HUMAN_REVIEW"          # REPAIR | REPLACE | REFUND | DENY | HUMAN_REVIEW
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    similar_case_count: int = 0
