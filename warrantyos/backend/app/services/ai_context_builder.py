"""
AI Context Builder — Part 2.2
Combines Claim + Warranty + Evidence + Historical + Policy + Risk into sanitized AIAnalysisContext.
This context is what future LLM/RocketRide will consume. Offline, deterministic, auditable.
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.product import Product, ProductSerial, WarrantyPolicy
from app.schemas.evidence_ai import AIAnalysisContext, NormalizedEvidence, SimilarCaseResult, RiskSignal, PolicyKnowledgeItem
from app.services.evidence_service import build_normalized_evidence
from app.services.document_extractor import MockDocumentExtractor
from app.services.historical_case_service import find_similar_cases
from app.services.policy_knowledge_service import retrieve_policy_knowledge
from app.services.risk_signal_service import generate_risk_signals

logger = logging.getLogger("warrantyos.ai_context")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [ai_context] claim_id=%(claim_id)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Explicit sanitization boundary
FORBIDDEN_FIELDS = {"password", "password_hash", "hashed_password", "jwt", "token", "email", "phone", "file_path", "absolute_path", "api_key", "session"}


def sanitize_for_ai_context(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove forbidden fields, ensure no PII/file paths enter AI context.
    """
    sanitized = {}
    for k, v in data.items():
        low_k = k.lower()
        if any(forbidden in low_k for forbidden in FORBIDDEN_FIELDS):
            continue
        # Also check value if it's a path-like string containing "/uploads"
        if isinstance(v, str) and "/uploads" in v:
            continue
        # Recursively sanitize dicts
        if isinstance(v, dict):
            sanitized[k] = sanitize_for_ai_context(v)
        elif isinstance(v, list):
            # Sanitize list of dicts
            sanitized[k] = [sanitize_for_ai_context(x) if isinstance(x, dict) else x for x in v]
        else:
            sanitized[k] = v
    return sanitized


def build_ai_context(db: Session, claim: Claim) -> AIAnalysisContext:
    """
    Build structured AIAnalysisContext for a claim.
    All sub-components are deterministic and offline.
    """
    # 1. Claim sanitized summary (no PII)
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
    claim_summary = {
        "claim_code": claim.claim_code,
        "product_name": product.name if product else None,
        "product_category": product.category if product else None,
        "serial_number": serial.serial_number if serial else None,
        "fault_category": claim.fault_category,
        "fault_description": claim.fault_description,
        "purchase_date": str(claim.purchase_date) if claim.purchase_date else None,
        "status": claim.status,
        "created_at": str(claim.created_at) if claim.created_at else None,
    }
    claim_summary = sanitize_for_ai_context(claim_summary)

    # 2. Warranty result (deterministic, authoritative)
    warranty = {
        "eligible": claim.warranty_eligible,
        "reason": claim.eligibility_reason,
        "warranty_active": claim.warranty_eligible if claim.warranty_eligible is not None else None,
        "exclusions_triggered": claim.exclusions_triggered or [],
        "missing_information": claim.missing_information or [],
        "purchase_date": str(claim.purchase_date) if claim.purchase_date else None,
    }
    warranty = sanitize_for_ai_context(warranty)

    # 3. Normalized evidence + document extraction
    extractor = MockDocumentExtractor()
    extracted = extractor.extract(db, claim)
    normalized = build_normalized_evidence(db, claim, extracted_document=extracted)
    # Evidence is already sanitized (no file paths), but ensure
    # Convert to dict for context
    evidence_dict = normalized.model_dump()
    evidence_dict = sanitize_for_ai_context(evidence_dict)

    # 4. Similar cases
    similar = find_similar_cases(db, claim, top_k=5)
    similar_dict = similar.model_dump()
    # Similar cases are already anonymized (no customer PII)

    # 5. Policy context
    policy_items = retrieve_policy_knowledge(db, claim, top_k=5)
    policy_dict = [item.model_dump() for item in policy_items]

    # 6. Risk signals
    risk_signals = generate_risk_signals(db, claim, normalized)
    risk_dict = [s.model_dump() for s in risk_signals]

    # Build final context
    context = AIAnalysisContext(
        claim=claim_summary,
        warranty=warranty,
        evidence=NormalizedEvidence(**evidence_dict) if isinstance(evidence_dict, dict) else normalized,
        similar_cases=SimilarCaseResult(**similar_dict),
        policy_context=policy_items,
        risk_signals=risk_signals,
        sanitized=True,
        version="2.2"
    )

    # Structured log (no secrets)
    logger.info(
        "AI_CONTEXT_BUILT",
        extra={
            "claim_id": claim.id,
        }
    )
    # Also log counts (use same logger with extra to satisfy formatter)
    logger.info(
        f"AI_CONTEXT_BUILT claim_id={claim.id} evidence_count={len(normalized.items)} missing_count={len(normalized.completeness.missing)} similar_cases={len(similar.top_cases)} policy_matches={len(policy_items)} risk_signals={len(risk_signals)}",
        extra={"claim_id": claim.id},
    )

    return context
