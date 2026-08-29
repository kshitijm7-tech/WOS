"""
Review Workflow — Part 2.3
Human review governance for AI decisions.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role, get_current_user
from app.models.user import User, Admin
from app.models.claim import Claim, ClaimDecision, ClaimReview, ClaimTimeline
from app.schemas.governance import ReviewRequest, ReviewResponse
from app.services.status_machine import assert_valid_transition

router = APIRouter(tags=["reviews"])


def _get_claim_or_404(db: Session, claim_id: int) -> Claim:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def _get_latest_decision(db: Session, claim_id: int) -> ClaimDecision:
    dec = db.query(ClaimDecision).filter(ClaimDecision.claim_id == claim_id).order_by(ClaimDecision.created_at.desc()).first()
    if not dec:
        raise HTTPException(status_code=404, detail="No AI decision found for this claim. Run analysis first.")
    return dec


@router.get("/api/admin/claims/{claim_id}/review", response_model=ReviewResponse)
def get_review(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    claim = _get_claim_or_404(db, claim_id)
    # Return latest review if exists, else 404 with status NOT_REQUIRED
    review = db.query(ClaimReview).filter(ClaimReview.claim_id == claim_id).order_by(ClaimReview.created_at.desc()).first()
    if not review:
        raise HTTPException(status_code=404, detail="No review found for this claim.")
    return review


@router.post("/api/admin/claims/{claim_id}/review", response_model=ReviewResponse, status_code=201)
def create_review(
    claim_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    claim = _get_claim_or_404(db, claim_id)
    decision = _get_latest_decision(db, claim_id)

    # Find admin
    admin = db.query(Admin).filter(Admin.user_id == current_user.id).first()
    if not admin:
        raise HTTPException(status_code=403, detail="Admin profile not found.")

    # Check existing review for idempotency
    existing = db.query(ClaimReview).filter(ClaimReview.claim_id == claim_id, ClaimReview.claim_decision_id == decision.id).first()
    # For APPROVE/REJECT, if already exists with same action, return existing (idempotent)
    # But if trying to approve again with different action, should we allow? For Part 2.3, we allow override via OVERRIDE action

    # Validate action
    action = payload.action.upper()
    allowed = {"APPROVE", "REJECT", "REQUEST_INFORMATION", "OVERRIDE", "ESCALATE", "START_REVIEW"}
    if action not in allowed:
        raise HTTPException(status_code=422, detail=f"Invalid action. Allowed: {allowed}")

    # OVERRIDE requires decision and reason
    if action == "OVERRIDE":
        if not payload.decision:
            raise HTTPException(status_code=422, detail="Override requires 'decision' field.")
        if not payload.reason:
            raise HTTPException(status_code=422, detail="Override requires 'reason' field.")
        # Check that AI decision is being overridden
        if payload.decision == decision.recommendation:
            raise HTTPException(status_code=400, detail="Override decision must differ from AI recommendation.")

    # If action is APPROVE/REJECT and claim already has a completed review for this decision, check idempotency
    # For simplicity, we allow multiple reviews but check for duplicate final state
    # Check if claim status is already terminal and review already completed
    latest_review = db.query(ClaimReview).filter(ClaimReview.claim_id == claim_id).order_by(ClaimReview.created_at.desc()).first()
    if latest_review and latest_review.status == "COMPLETED" and latest_review.action == action and latest_review.claim_decision_id == decision.id:
        # Idempotent: return existing
        return latest_review

    # Determine new status and human_decision
    status_map = {
        "APPROVE": "COMPLETED",
        "REJECT": "COMPLETED",
        "REQUEST_INFORMATION": "REQUESTED_INFORMATION",
        "OVERRIDE": "OVERRIDDEN",
        "ESCALATE": "IN_PROGRESS",
        "START_REVIEW": "IN_PROGRESS",
    }
    new_status = status_map.get(action, "PENDING")
    human_decision = payload.decision or action
    is_override = action == "OVERRIDE"

    # For REQUEST_INFORMATION, set claim status to MORE_INFORMATION_REQUIRED via status_machine
    # For APPROVE/REJECT, we may want to transition claim status accordingly, but keep it separate from AI status
    # Here we handle review record creation and timeline, and optionally update claim status if needed

    # Create review
    review = ClaimReview(
        claim_id=claim.id,
        reviewed_by_admin_id=admin.id,
        claim_decision_id=decision.id,
        action=action,
        notes=payload.notes or payload.reason,
        status=new_status,
        human_decision=human_decision,
        override=is_override,
        override_reason=payload.reason if is_override else None,
    )
    db.add(review)

    # Update decision final_outcome if approved/rejected/override
    if action in ("APPROVE", "REJECT", "OVERRIDE"):
        # Set final_outcome to human decision
        decision.final_outcome = human_decision
        # Also store override info in decision if needed

    # Timeline events
    event_map = {
        "APPROVE": "AI_REVIEW_APPROVED",
        "REJECT": "AI_REVIEW_REJECTED",
        "REQUEST_INFORMATION": "AI_REVIEW_REQUESTED_INFORMATION",
        "OVERRIDE": "AI_DECISION_OVERRIDDEN",
        "ESCALATE": "AI_REVIEW_STARTED",
        "START_REVIEW": "AI_REVIEW_STARTED",
    }
    event_type = event_map.get(action, "AI_REVIEW_STARTED")
    db.add(ClaimTimeline(
        claim_id=claim.id,
        event_type=event_type,
        actor=f"admin:{current_user.email}",
        notes=payload.notes or payload.reason or f"Review {action} for AI {decision.recommendation} -> {human_decision}",
        event_metadata={
            "claim_decision_id": decision.id,
            "ai_recommendation": decision.recommendation,
            "human_decision": human_decision,
            "override": is_override,
            "override_reason": payload.reason if is_override else None,
        }
    ))

    # Optionally update claim status if review requests information
    if action == "REQUEST_INFORMATION":
        # Transition claim to MORE_INFORMATION_REQUIRED if not already
        try:
            from app.services.status_machine import assert_valid_transition
            if claim.status != "MORE_INFORMATION_REQUIRED":
                assert_valid_transition(claim.status, "MORE_INFORMATION_REQUIRED")
                old = claim.status
                claim.status = "MORE_INFORMATION_REQUIRED"
                db.add(ClaimTimeline(
                    claim_id=claim.id,
                    event_type="STATUS_CHANGED",
                    actor=f"admin:{current_user.email}",
                    notes=f"Status {old} -> MORE_INFORMATION_REQUIRED (review requested info)",
                    event_metadata={"from": old, "to": "MORE_INFORMATION_REQUIRED", "reason": "review"}
                ))
        except Exception:
            pass  # If invalid transition, just keep review without status change

    db.commit()
    db.refresh(review)
    return review


@router.patch("/api/admin/claims/{claim_id}/review/{review_id}", response_model=ReviewResponse)
def update_review(
    claim_id: int,
    review_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    # For Part 2.3, PATCH is used to update a pending review (e.g., complete it)
    # For simplicity, we treat PATCH as updating notes/status if review is PENDING/IN_PROGRESS
    claim = _get_claim_or_404(db, claim_id)
    review = db.query(ClaimReview).filter(ClaimReview.id == review_id, ClaimReview.claim_id == claim_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    # Check if review is already completed and trying to change
    if review.status == "COMPLETED" and payload.action in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=409, detail="Claim review is already completed.")

    # Update
    if payload.notes:
        review.notes = payload.notes
    if payload.action:
        review.action = payload.action.upper()
    review.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return review
