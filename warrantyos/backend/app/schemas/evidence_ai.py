"""
Pydantic schemas for Part 2.2 Evidence & Knowledge Intelligence
Normalized evidence, extracted documents, completeness, quality
"""
from datetime import date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

EvidenceQuality = Literal["AVAILABLE", "MISSING", "OPTIONAL", "INVALID"]
EvidenceType = Literal["invoice", "photo", "video", "document", "serial", "fault_description", "purchase_date"]


class EvidenceItem(BaseModel):
    evidence_type: str  # invoice | photo | video | document | serial | fault_description | purchase_date
    present: bool
    quality: EvidenceQuality
    confidence: float = Field(ge=0, le=1)
    source: str  # claim_evidence | claim | product_serial | warranty_policy
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractedDocument(BaseModel):
    invoice_number: Optional[str] = None
    purchase_date: Optional[date] = None
    seller: Optional[str] = None
    product_name: Optional[str] = None
    serial_number: Optional[str] = None
    amount: Optional[float] = None
    customer_name: Optional[str] = None
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    source: str = "mock"  # mock | ocr | manual
    raw_fields: Dict[str, Any] = Field(default_factory=dict)


class EvidenceCompletenessItem(BaseModel):
    evidence_type: str
    status: EvidenceQuality
    required: bool
    present: bool
    reason: Optional[str] = None


class EvidenceCompleteness(BaseModel):
    items: List[EvidenceCompletenessItem]
    missing: List[str]  # list of missing required evidence types
    optional_missing: List[str]
    overall: Literal["COMPLETE", "PARTIAL", "INCOMPLETE"]


class NormalizedEvidence(BaseModel):
    items: List[EvidenceItem]
    completeness: EvidenceCompleteness
    extracted_document: Optional[ExtractedDocument] = None
    total_present: int
    total_required: int


class HistoricalCaseOut(BaseModel):
    case_id: int
    product_category: Optional[str] = None
    product_name: Optional[str] = None
    fault_type: Optional[str] = None
    warranty_status: Optional[str] = None
    claim_outcome: Optional[str] = None
    evidence_profile: Optional[str] = None
    summary: Optional[str] = None
    similarity_score: Optional[float] = None
    matched_features: Optional[List[str]] = None
    relevance_reason: Optional[str] = None

    class Config:
        from_attributes = True


class SimilarCaseResult(BaseModel):
    similar_case_count: int
    top_cases: List[HistoricalCaseOut]


class PolicyKnowledgeItem(BaseModel):
    policy_id: int
    product_id: int
    title: str  # e.g., "Accidental Damage Exclusion"
    category: str  # coverage | non_coverage | accidental_damage | liquid_damage | etc.
    content: str
    relevance: float = Field(ge=0, le=1)
    reason: str


class RiskSignal(BaseModel):
    code: str  # e.g., MULTIPLE_RECENT_CLAIMS
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    description: str
    source: str  # claim_history | evidence | warranty | etc.
    confidence: float = Field(ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIAnalysisContext(BaseModel):
    claim: Dict[str, Any]  # sanitized claim summary (no PII)
    warranty: Dict[str, Any]  # deterministic WarrantyResult (sanitized)
    evidence: NormalizedEvidence
    similar_cases: SimilarCaseResult
    policy_context: List[PolicyKnowledgeItem]
    risk_signals: List[RiskSignal]
    # For audit
    sanitized: bool = True
    version: str = "2.2"
