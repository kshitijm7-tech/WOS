"""
Decision Governance Service — Part 2.3
Deterministic, explainable, auditable. No AI.
"""

from typing import List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.claim import Claim, ClaimDecision
from app.schemas.evidence_ai import AIAnalysisContext
from app.schemas.governance import (
    ConfidenceBand, Conflict, ConflictSeverity, DecisionExplanation, Scorecard,
    DecisionGovernanceResult, DecisionGovernanceStatus
)
from app.services.decision_conflict import detect_conflicts

# Configurable thresholds
@dataclass
class DecisionThresholds:
    auto_suggestion_min_confidence: float = 0.85
    human_review_confidence: float = 0.60
    high_confidence: float = 0.85
    medium_confidence: float = 0.60

THRESHOLDS = DecisionThresholds()

def get_confidence_band(confidence: float) -> ConfidenceBand:
    if confidence >= THRESHOLDS.high_confidence:
        return ConfidenceBand.HIGH
    if confidence >= THRESHOLDS.medium_confidence:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW

def _risk_level_from_signals(risk_signals) -> str:
    if not risk_signals:
        return "LOW"
    if any(getattr(r, 'severity', '') == "HIGH" for r in risk_signals):
        return "HIGH"
    if any(getattr(r, 'severity', '') == "MEDIUM" for r in risk_signals):
        return "MEDIUM"
    return "LOW"

def _build_scorecard(
    evidence_completeness: str,
    warranty_consistent: bool,
    policy_alignment: float,
    historical_similarity: float,
    risk_level: str,
    claim_consistent: bool,
) -> Scorecard:
    # Deterministic scorecard weights (as per spec)
    # Evidence 25%, Warranty 20%, Policy 20%, Historical 15%, Risk 10%, Claim 10%
    # Map completeness to score
    completeness_map = {"COMPLETE": 1.0, "PARTIAL": 0.6, "INCOMPLETE": 0.2}
    evidence_score = completeness_map.get(evidence_completeness, 0.5)
    warranty_score = 1.0 if warranty_consistent else 0.3
    # policy_alignment already 0-1
    # historical_similarity 0-1 (take top case score or 0.5)
    # risk: LOW=1.0, MEDIUM=0.6, HIGH=0.2
    risk_map = {"LOW": 1.0, "MEDIUM": 0.6, "HIGH": 0.2}
    risk_score = risk_map.get(risk_level, 0.5)
    claim_score = 1.0 if claim_consistent else 0.5

    overall = (
        evidence_score * 0.25 +
        warranty_score * 0.20 +
        policy_alignment * 0.20 +
        historical_similarity * 0.15 +
        risk_score * 0.10 +
        claim_score * 0.10
    )
    return Scorecard(
        evidence_completeness=evidence_score,
        warranty_consistency=warranty_score,
        policy_alignment=policy_alignment,
        historical_similarity=historical_similarity,
        risk_profile=risk_score,
        claim_consistency=claim_score,
        overall_decision_score=round(overall, 3)
    )

def _build_explanation(
    claim: Claim,
    ai_decision: ClaimDecision,
    context: AIAnalysisContext,
    conflicts: List[Conflict],
    band: ConfidenceBand,
    risk_level: str,
) -> DecisionExplanation:
    # Supporting evidence: from AI decision evidence + warranty active + photo/invoice available
    supporting = list(ai_decision.evidence or [])
    # Ensure we have some supporting from warranty
    if claim.warranty_eligible:
        supporting.append(f"Warranty active: {claim.eligibility_reason}")
    # Add historical
    if context.similar_cases.top_cases:
        supporting.append(f"{len(context.similar_cases.top_cases)} similar historical cases found")

    # Contradicting: from conflicts and risk
    contradicting = []
    for c in conflicts:
        contradicting.append(f"{c.conflict_code}: {c.description}")
    for rs in context.risk_signals:
        if rs.severity == "HIGH":
            contradicting.append(f"High risk: {rs.code}")

    # Policy references
    policy_refs = [f"{p.title} (relevance {p.relevance})" for p in context.policy_context[:3]]

    # Historical references
    hist_refs = [f"Case {c.case_id} ({c.claim_outcome})" for c in context.similar_cases.top_cases[:3]]

    # Risk factors
    risk_factors = [f"{r.code}: {r.description}" for r in context.risk_signals]

    # Reasoning factors
    reasoning = [
        f"Warranty is {'eligible' if claim.warranty_eligible else 'not eligible'}",
        f"Evidence completeness: {context.evidence.completeness.overall}",
        f"Confidence band: {band.value} ({ai_decision.confidence})",
        f"Risk level: {risk_level}",
        f"Validation: {ai_decision.validation_status}",
    ]
    if conflicts:
        reasoning.append(f"Conflicts detected: {len(conflicts)}")

    summary = f"AI recommends {ai_decision.recommendation} with {band.value} confidence ({ai_decision.confidence}). " + \
              (f"Human review required due to {', '.join([c.conflict_code for c in conflicts])}." if conflicts else "No conflicts.")

    confidence_exp = f"Confidence {ai_decision.confidence} is {band.value} (thresholds: HIGH ≥{THRESHOLDS.high_confidence}, MEDIUM ≥{THRESHOLDS.medium_confidence})."

    return DecisionExplanation(
        summary=summary,
        reasoning_factors=reasoning,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        policy_references=policy_refs,
        historical_case_references=hist_refs,
        risk_factors=risk_factors,
        confidence_explanation=confidence_exp
    )

def evaluate_governance(
    db: Session,
    claim: Claim,
    ai_decision: ClaimDecision,
    context: AIAnalysisContext,
) -> DecisionGovernanceResult:
    """
    Deterministic governance evaluation.
    Returns structured result with explicit review reasons.
    """
    # Confidence band
    band = get_confidence_band(float(ai_decision.confidence or 0))

    # Risk level
    risk_level = "LOW"
    if ai_decision.risk_flags:
        # Use context risk signals for more accurate
        if any(getattr(r, 'severity', '') == "HIGH" for r in context.risk_signals):
            risk_level = "HIGH"
        elif any(getattr(r, 'severity', '') == "MEDIUM" for r in context.risk_signals):
            risk_level = "MEDIUM"
    # Also check decision's risk_flags
    if ai_decision.risk_flags and risk_level == "LOW":
        risk_level = "MEDIUM"

    # Evidence completeness
    completeness = context.evidence.completeness.overall if context.evidence and context.evidence.completeness else "UNKNOWN"

    # Conflicts
    conflicts = detect_conflicts(db, claim, ai_decision.recommendation)

    # Human review triggers (10 rules)
    review_reasons: List[str] = []

    # 1. validator INVALID
    if ai_decision.validation_status == "INVALID":
        review_reasons.append("AI validator returned INVALID")
    # 2. confidence < threshold
    if float(ai_decision.confidence) < THRESHOLDS.human_review_confidence:
        review_reasons.append(f"Confidence {ai_decision.confidence} below threshold {THRESHOLDS.human_review_confidence}")
    # 3. HIGH risk
    if risk_level == "HIGH":
        review_reasons.append("HIGH risk level")
    # 4. contradictory evidence (conflicts)
    if conflicts:
        review_reasons.append(f"Conflicts detected: {', '.join([c.conflict_code for c in conflicts])}")
    # 5. missing evidence for consequential decision
    if completeness == "INCOMPLETE" and ai_decision.recommendation in ("REPAIR", "REPLACE", "DENY"):
        review_reasons.append(f"Required evidence missing ({', '.join(context.evidence.completeness.missing)}) for {ai_decision.recommendation}")
    # 6. AI conflicts with warranty
    for c in conflicts:
        if c.conflict_code == "WARRANTY_CONFLICT":
            review_reasons.append(f"AI {ai_decision.recommendation} conflicts with warranty_eligible={claim.warranty_eligible}")
            break
    # 7. recommendation is HUMAN_REVIEW
    if ai_decision.recommendation == "HUMAN_REVIEW":
        review_reasons.append("AI explicitly requested HUMAN_REVIEW")
    # 8. policy conflicting/ambiguous (if policy retrieval has low relevance and contradicting)
    if context.policy_context and any(p.relevance < 0.3 for p in context.policy_context):
        # Not strong, skip unless needed
        pass
    # 9. evidence extraction confidence insufficient
    if context.evidence.extracted_document and context.evidence.extracted_document.extraction_confidence < 0.5:
        review_reasons.append(f"Evidence extraction confidence low ({context.evidence.extracted_document.extraction_confidence})")
    # 10. multiple significant risk signals
    if len([r for r in context.risk_signals if r.severity in ("MEDIUM","HIGH")]) >= 2:
        review_reasons.append(f"Multiple risk signals ({len(context.risk_signals)})")

    requires_review = len(review_reasons) > 0
    # Also if validator says INVALID, must review
    if ai_decision.validation_status == "INVALID":
        requires_review = True

    # Determine governance status
    if ai_decision.validation_status == "INVALID":
        gov_status = "PENDING_HUMAN_REVIEW"
    elif requires_review:
        gov_status = "PENDING_HUMAN_REVIEW"
    elif ai_decision.recommendation == "MORE_INFORMATION_REQUIRED":
        gov_status = "MORE_INFORMATION_REQUIRED"
    else:
        # Check confidence band for auto suggestion
        if band == ConfidenceBand.HIGH and not requires_review and ai_decision.validation_status == "VALID":
            gov_status = "AI_SUGGESTION"
        else:
            gov_status = "PENDING_HUMAN_REVIEW" if requires_review else "AI_SUGGESTION"

    # For Part 2.3, we map to existing statuses where possible
    # Use DecisionGovernanceStatus enum values: AI_SUGGESTION, PENDING_HUMAN_REVIEW, etc.
    # If no review needed and valid, it's AI_SUGGESTION

    # Scorecard
    # Policy alignment: average relevance of policy_context or 0.5
    policy_alignment = sum(p.relevance for p in context.policy_context) / len(context.policy_context) if context.policy_context else 0.5
    # Historical similarity: top case score or 0.5
    hist_score = context.similar_cases.top_cases[0].similarity_score if context.similar_cases.top_cases else 0.5
    warranty_consistent = not any(c.conflict_code == "WARRANTY_CONFLICT" for c in conflicts)
    claim_consistent = len(conflicts) == 0

    scorecard = _build_scorecard(
        evidence_completeness=completeness,
        warranty_consistent=warranty_consistent,
        policy_alignment=policy_alignment,
        historical_similarity=hist_score,
        risk_level=risk_level,
        claim_consistent=claim_consistent,
    )

    # Explanation
    explanation = _build_explanation(claim, ai_decision, context, conflicts, band, risk_level)

    return DecisionGovernanceResult(
        recommendation=ai_decision.recommendation,
        confidence=float(ai_decision.confidence),
        confidence_band=band,
        decision_score=scorecard.overall_decision_score,
        risk_level=risk_level,  # type: ignore
        evidence_completeness=completeness,  # type: ignore
        requires_human_review=requires_review,
        review_reasons=review_reasons,
        conflicts=conflicts,
        explanation=explanation,
        scorecard=scorecard,
        validation_status=ai_decision.validation_status or "UNKNOWN",
        governance_status=gov_status,  # type: ignore
    )
