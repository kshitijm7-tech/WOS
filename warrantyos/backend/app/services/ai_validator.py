"""
Deterministic validator for AI pipeline output — Part 2.1
No AI, pure Python. Never trust MockRocketRideClient blindly.
"""

import sys
from pathlib import Path

# Ensure rocketrider sibling importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from typing import List, Dict, Any, Tuple
from rocketrider.pipeline import STAGES, ClaimPipelineResult

ALLOWED_RECOMMENDATIONS = {"REPAIR", "REPLACE", "DENY", "MORE_INFORMATION_REQUIRED", "HUMAN_REVIEW"}
ALLOWED_VALIDATION = {"VALID", "INVALID", "REQUIRES_HUMAN_REVIEW"}

# Required stages as per pipeline.py
REQUIRED_STAGES = set(STAGES)  # 6 stages

# Part 2.2 enriched aliases (kept for backward compat and spec alignment)
ALLOWED_EXTRA_STAGES = {"POLICY_INTERPRETATION", "SIMILAR_CASES", "RISK_ASSESSMENT", "FRAUD_RISK", "RECOMMENDATION"}
ALLOWED_STAGES = REQUIRED_STAGES | ALLOWED_EXTRA_STAGES

# Human review triggers (deterministic)
LOW_CONFIDENCE_THRESHOLD = 0.6
HUMAN_REVIEW_RECOMMENDATION = "HUMAN_REVIEW"


def _is_list_of_strings(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate_pipeline_result(result: ClaimPipelineResult) -> Tuple[str, List[Dict[str, Any]], bool, str]:
    """
    Returns: (validation_status, validation_errors, requires_human_review, review_reason)
    validation_status ∈ {VALID, INVALID, REQUIRES_HUMAN_REVIEW}
    """
    errors: List[Dict[str, Any]] = []
    requires_review = False
    review_reasons: List[str] = []

    # 1. recommendation allowed
    if not result.recommendation or result.recommendation not in ALLOWED_RECOMMENDATIONS:
        errors.append({"field": "recommendation", "error": f"Invalid recommendation '{result.recommendation}'. Allowed: {sorted(ALLOWED_RECOMMENDATIONS)}"})

    # 2. confidence exists
    if result.confidence is None:
        errors.append({"field": "confidence", "error": "confidence is required"})

    # 3. confidence bounds 0–0.97
    try:
        conf = float(result.confidence) if result.confidence is not None else None
        if conf is not None and (conf < 0 or conf > 0.97):
            errors.append({"field": "confidence", "error": f"confidence {conf} out of bounds [0, 0.97]"})
    except Exception:
        errors.append({"field": "confidence", "error": "confidence must be numeric"})

    # 4. required stages exist
    missing_stages = REQUIRED_STAGES - set(result.stage_outputs.keys())
    if missing_stages:
        errors.append({"field": "stage_outputs", "error": f"Missing required stages: {sorted(missing_stages)}"})

    # 5. stage names valid (allow enriched aliases)
    for stage in result.stage_outputs.keys():
        if stage not in ALLOWED_STAGES:
            errors.append({"field": "stage_outputs", "error": f"Invalid stage name '{stage}'. Allowed: {sorted(ALLOWED_STAGES)}"})

    # 6. no malformed stage output (each stage result must be dict)
    for stage, out in result.stage_outputs.items():
        if not isinstance(out, dict):
            errors.append({"field": f"stage_outputs.{stage}", "error": "Stage output must be dict"})

    # 7. missing_information structurally valid
    if not _is_list_of_strings(result.missing_information):
        errors.append({"field": "missing_information", "error": "must be list of strings"})

    # 8. risk_flags structurally valid
    if not _is_list_of_strings(result.risk_flags):
        errors.append({"field": "risk_flags", "error": "must be list of strings"})

    # 9. final recommendation consistency with human-review conditions
    # These do NOT make it INVALID, but trigger REQUIRES_HUMAN_REVIEW
    if result.recommendation == HUMAN_REVIEW_RECOMMENDATION:
        requires_review = True
        review_reasons.append("AI requested human review")

    if result.missing_information:
        requires_review = True
        review_reasons.append(f"Missing information: {', '.join(result.missing_information)}")

    if result.risk_flags:
        requires_review = True
        review_reasons.append(f"Risk flags: {', '.join(result.risk_flags)}")

    # low confidence
    try:
        if result.confidence is not None and float(result.confidence) < LOW_CONFIDENCE_THRESHOLD:
            requires_review = True
            review_reasons.append(f"Low confidence {result.confidence} < {LOW_CONFIDENCE_THRESHOLD}")
    except Exception:
        pass

    # If errors exist, INVALID takes precedence over REQUIRES_HUMAN_REVIEW
    if errors:
        return "INVALID", errors, True, "; ".join(review_reasons) or "Validation failed"

    if requires_review:
        return "REQUIRES_HUMAN_REVIEW", [], True, "; ".join(review_reasons)

    return "VALID", [], False, ""


def validate_for_human_review(validation_status: str, recommendation: str, confidence: float, missing: List[str], risk_flags: List[str]) -> Tuple[bool, str]:
    """
    Helper to decide human review from decision fields (used after persistence).
    """
    reasons = []
    if validation_status == "INVALID":
        reasons.append("Validation failed")
    if validation_status == "REQUIRES_HUMAN_REVIEW":
        reasons.append("Validator requires human review")
    if recommendation == HUMAN_REVIEW_RECOMMENDATION:
        reasons.append("AI recommended HUMAN_REVIEW")
    if missing:
        reasons.append(f"Missing: {', '.join(missing)}")
    if risk_flags:
        reasons.append(f"Risk: {', '.join(risk_flags)}")
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        reasons.append(f"Low confidence {confidence}")
    if reasons:
        return True, "; ".join(reasons)
    return False, ""
