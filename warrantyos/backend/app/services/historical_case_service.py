"""
Historical Case Intelligence — Part 2.2
Deterministic retrieval without embeddings/pgvector.
Uses HistoricalCase table (seeded corpus) and weighted similarity.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.intelligence import HistoricalCase
from app.models.product import Product
from app.models.claim import Claim, ClaimEvidence
from app.schemas.evidence_ai import HistoricalCaseOut, SimilarCaseResult

# Configurable weights (must sum to 1.0)
WEIGHTS = {
    "product_category": 0.30,
    "product_family": 0.25,
    "fault_similarity": 0.25,
    "evidence_profile": 0.10,
    "claim_characteristics": 0.10,
}


def _tokenize(text: str) -> set:
    if not text:
        return set()
    return set(text.lower().split())


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _fault_similarity(claim_fault: str, claim_cat: str, case_fault: str, case_cat: str) -> float:
    # Combine fault_description keywords + fault_category
    claim_tokens = _tokenize(claim_fault) | _tokenize(claim_cat or "")
    case_tokens = _tokenize(case_fault) | _tokenize(case_cat or "")
    return _jaccard(claim_tokens, case_tokens)


def find_similar_cases(db: Session, claim: Claim, top_k: int = 5) -> SimilarCaseResult:
    """
    Retrieve top K similar historical cases deterministically.
    Returns SimilarCaseResult with top_cases including similarity_score and matched_features.
    """
    # Load all historical cases (for 20-50, full scan is fine)
    cases = db.query(HistoricalCase).all()
    if not cases:
        return SimilarCaseResult(similar_case_count=0, top_cases=[])

    # Load claim's product for category
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    claim_category = product.category if product else ""
    claim_product_id = claim.product_id

    # Evidence profile for claim
    evidences = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
    claim_has_invoice = any(e.evidence_type == "INVOICE" for e in evidences)
    claim_has_photo = any(e.evidence_type == "PHOTO" for e in evidences)
    claim_evidence_profile = f"invoice:{claim_has_invoice},photo:{claim_has_photo}"

    scored = []
    for case in cases:
        case_product = db.query(Product).filter(Product.id == case.product_id).first()
        case_category = case_product.category if case_product else ""
        case_product_id = case.product_id

        # 1. Product category (30%)
        cat_score = 1.0 if claim_category and claim_category == case_category else 0.0

        # 2. Product/family (25%) — exact product match
        family_score = 1.0 if claim_product_id == case_product_id else 0.0

        # 3. Fault similarity (25%)
        fault_score = _fault_similarity(claim.fault_description or "", claim.fault_category or "", case.summary or "", case.fault_category or "")

        # 4. Evidence profile (10%) — simple: both have similar summary length? For now, use claim_has_photo vs case's evidence_profile string match
        # HistoricalCase doesn't have evidence_profile column, so we approximate via summary length similarity
        # We'll store evidence_profile in HistoricalCase.summary as JSON or just use 0.5 as placeholder
        # For Part 2.2, we keep it simple: 0.5 if both have fault_category, else 0
        evidence_score = 0.5

        # 5. Claim characteristics (10%) — warranty status not in HistoricalCase, use placeholder
        char_score = 0.5

        total = (
            WEIGHTS["product_category"] * cat_score +
            WEIGHTS["product_family"] * family_score +
            WEIGHTS["fault_similarity"] * fault_score +
            WEIGHTS["evidence_profile"] * evidence_score +
            WEIGHTS["claim_characteristics"] * char_score
        )

        matched = []
        if cat_score == 1.0:
            matched.append("Same product category")
        if family_score == 1.0:
            matched.append("Same product")
        if fault_score > 0.3:
            matched.append(f"Similar fault (score {fault_score:.2f})")
        if not matched:
            matched.append("General similarity")

        # Determine relevance reason
        relevance = f"Matched: {', '.join(matched)}"
        # Historical outcome is case.resolution
        scored.append((total, case, matched, relevance))

    # Sort by score desc, deterministic tie-break by case_id
    scored.sort(key=lambda x: (-x[0], x[1].id))

    top = scored[:top_k]
    top_cases = []
    for score, case, matched, relevance in top:
        case_product = db.query(Product).filter(Product.id == case.product_id).first()
        top_cases.append(HistoricalCaseOut(
            case_id=case.id,
            product_category=case_product.category if case_product else None,
            product_name=case_product.name if case_product else None,
            fault_type=case.fault_category,
            warranty_status=None,  # not in HistoricalCase
            claim_outcome=case.resolution,
            evidence_profile=None,
            summary=case.summary,
            similarity_score=round(score, 3),
            matched_features=matched,
            relevance_reason=relevance
        ))

    return SimilarCaseResult(similar_case_count=len(cases), top_cases=top_cases)
