"""
Historical Case Intelligence — Part 2.2/2.5
Deterministic retrieval by default, with optional semantic retrieval via EmbeddingProvider + VectorStore.
Hybrid: semantic 50% + structured 50% when vector store available, else Jaccard fallback.
All offline, deterministic, no PII.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.intelligence import HistoricalCase
from app.models.product import Product
from app.models.claim import Claim, ClaimEvidence
from app.schemas.evidence_ai import HistoricalCaseOut, SimilarCaseResult

# Configurable weights for Part 2.6 scoring model (must sum to 1.0)
SCORING_WEIGHTS = {
    "semantic_similarity": 0.40,
    "product_category": 0.20,
    "product_family": 0.15,
    "fault_similarity": 0.15,
    "evidence_similarity": 0.05,
    "claim_metadata_similarity": 0.05,
}
WEIGHTS = SCORING_WEIGHTS  # alias for backwards compat


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


def _canonical_text(product_name: str, category: str, fault: str, summary: str) -> str:
    # Sanitized canonical representation for embedding (no PII)
    return f"{product_name or ''} {category or ''} {fault or ''} {summary or ''}".strip().lower()


def find_similar_cases(db: Session, claim: Claim, top_k: int = 5) -> SimilarCaseResult:
    """
    Retrieve top K similar historical cases using Part 2.6 explicit scoring model:
    - semantic_similarity: 0.40
    - product_category: 0.20
    - product_family: 0.15
    - fault_similarity: 0.15
    - evidence_similarity: 0.05
    - claim_metadata_similarity: 0.05
    Returns SimilarCaseResult with top_cases including semantic_score, structured_score, and similarity_score.
    """
    cases = db.query(HistoricalCase).all()
    if not cases:
        return SimilarCaseResult(similar_case_count=0, top_cases=[])

    # Try semantic retrieval first (if available)
    try:
        from app.services.embedding_provider import get_embedding_provider
        from app.services.vector_store import get_vector_store
        embedder = get_embedding_provider()
        store = get_vector_store()
        product = db.query(Product).filter(Product.id == claim.product_id).first()
        query_text = _canonical_text(
            product.name if product else "",
            product.category if product else "",
            f"{claim.fault_category or ''} {claim.fault_description or ''}",
            ""
        )
        for case in cases:
            case_product = db.query(Product).filter(Product.id == case.product_id).first()
            case_text = _canonical_text(
                case_product.name if case_product else "",
                case_product.category if case_product else "",
                f"{case.fault_category or ''} {case.summary or ''}",
                case.summary or ""
            )
            try:
                store.upsert(str(case.id), embedder.embed(case_text), {"case_id": case.id})
            except Exception:
                pass
        query_vec = embedder.embed(query_text)
        semantic_results = store.search(query_vec, top_k=top_k)
        semantic_map = {int(r["id"]): r["score"] for r in semantic_results}
        use_semantic = True
    except Exception:
        semantic_map = {}
        use_semantic = False

    product = db.query(Product).filter(Product.id == claim.product_id).first()
    claim_category = product.category if product else ""
    claim_product_id = claim.product_id

    evidences = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
    claim_has_invoice = any(e.evidence_type == "INVOICE" for e in evidences)
    claim_has_photo = any(e.evidence_type == "PHOTO" for e in evidences)

    scored = []
    for case in cases:
        case_product = db.query(Product).filter(Product.id == case.product_id).first()
        case_category = case_product.category if case_product else ""
        case_product_id = case.product_id

        # Explicit features
        cat_score = 1.0 if claim_category and claim_category == case_category else 0.0
        family_score = 1.0 if claim_product_id == case_product_id else 0.0
        fault_score = _fault_similarity(claim.fault_description or "", claim.fault_category or "", case.summary or "", case.fault_category or "")
        evidence_score = 0.8 if claim_has_invoice else 0.5
        meta_score = 0.5

        # Weighted structured score (normalized over structured weights sum = 0.60)
        structured_weights_sum = 0.20 + 0.15 + 0.15 + 0.05 + 0.05
        structured = (
            SCORING_WEIGHTS["product_category"] * cat_score +
            SCORING_WEIGHTS["product_family"] * family_score +
            SCORING_WEIGHTS["fault_similarity"] * fault_score +
            SCORING_WEIGHTS["evidence_similarity"] * evidence_score +
            SCORING_WEIGHTS["claim_metadata_similarity"] * meta_score
        ) / structured_weights_sum

        semantic = semantic_map.get(case.id, fault_score) if use_semantic else fault_score

        # Total combined score
        total_score = (
            SCORING_WEIGHTS["semantic_similarity"] * semantic +
            SCORING_WEIGHTS["product_category"] * cat_score +
            SCORING_WEIGHTS["product_family"] * family_score +
            SCORING_WEIGHTS["fault_similarity"] * fault_score +
            SCORING_WEIGHTS["evidence_similarity"] * evidence_score +
            SCORING_WEIGHTS["claim_metadata_similarity"] * meta_score
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

        relevance = f"Semantic: {semantic:.2f}, Structured: {structured:.2f}. Matched: {', '.join(matched)}"
        scored.append((total_score, semantic, structured, case, matched, relevance))

    scored.sort(key=lambda x: (-x[0], x[3].id))

    top = scored[:top_k]
    top_cases = []
    for total_score, semantic, structured, case, matched, relevance in top:
        case_product = db.query(Product).filter(Product.id == case.product_id).first()
        top_cases.append(HistoricalCaseOut(
            case_id=case.id,
            product_category=case_product.category if case_product else None,
            product_name=case_product.name if case_product else None,
            fault_type=case.fault_category,
            warranty_status=None,
            claim_outcome=case.resolution,
            evidence_profile=None,
            summary=case.summary,
            similarity_score=round(total_score, 3),
            semantic_score=round(semantic, 3),
            structured_score=round(structured, 3),
            matched_features=matched,
            relevance_reason=relevance
        ))

    return SimilarCaseResult(similar_case_count=len(cases), top_cases=top_cases)

