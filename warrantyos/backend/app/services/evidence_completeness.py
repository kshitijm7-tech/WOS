"""
Evidence Completeness Engine — Part 2.2
Deterministic AVAILABLE/MISSING/OPTIONAL/INVALID assessment.
This is a dedicated module per spec; logic lives in evidence_service for cohesion.
"""

from typing import List
from app.schemas.evidence_ai import EvidenceItem, EvidenceCompleteness
from app.services.evidence_service import assess_completeness as _assess

def assess_completeness(items: List[EvidenceItem]) -> EvidenceCompleteness:
    return _assess(items)
