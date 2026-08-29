"""
AI Analysis API — Part 2.1
Offline MockRocketRideClient only, BackgroundTasks, IDOR + RBAC, cached GET.
"""

import sys
from pathlib import Path

# Ensure rocketrider sibling importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.user import User, Customer
from app.models.claim import Claim, ClaimAnalysis, ClaimDecision, ClaimTimeline
from app.schemas.ai import AIAnalysisResponse, AIStageOutput, AIDecisionOut, AIAnalyzeStartResponse, AIAnalysisStatus

router = APIRouter(tags=["ai"])


def _get_claim_or_404(db: Session, claim_id: int) -> Claim:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return claim


def _verify_customer_access(claim: Claim, user: User, db: Session):
    if user.role.name in ("admin", "support"):
        return
    # customer must own claim
    cust = db.query(Customer).filter(Customer.user_id == user.id).first()
    if not cust or claim.customer_id != cust.id:
        raise HTTPException(status_code=403, detail="You don't have permission to access this claim.")


def _build_analysis_response(db: Session, claim: Claim) -> AIAnalysisResponse:
    # Fetch stages ordered by STAGES order
    from rocketrider.pipeline import STAGES
    stages = db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).all()
    # order by STAGES index
    stage_order = {s: i for i, s in enumerate(STAGES)}
    stages_sorted = sorted(stages, key=lambda x: stage_order.get(x.stage, 999))
    stage_outs = [AIStageOutput(stage=s.stage, result=s.result, created_at=s.created_at) for s in stages_sorted]

    # Latest decision (most recent)
    decision_row = db.query(ClaimDecision).filter(ClaimDecision.claim_id == claim.id).order_by(ClaimDecision.created_at.desc()).first()
    decision = None
    rec = None
    conf = None
    val_status = None
    req_review = None
    if decision_row:
        try:
            decision = AIDecisionOut.model_validate(decision_row)
            rec = decision.recommendation
            conf = decision.confidence
            val_status = decision.validation_status
            req_review = decision.requires_human_review
        except Exception:
            # If validation fails (should not), still return raw
            decision = None

    # Determine ai_analysis_status with default PENDING if null
    ai_status = claim.ai_analysis_status or "PENDING"
    # Map to enum, fallback to PENDING if invalid
    try:
        ai_status_enum = AIAnalysisStatus(ai_status)
    except Exception:
        ai_status_enum = AIAnalysisStatus.PENDING

    return AIAnalysisResponse(
        claim_id=claim.id,
        claim_code=claim.claim_code,
        ai_analysis_status=ai_status_enum,
        ai_analysis_requested_at=claim.ai_analysis_requested_at,
        ai_analysis_completed_at=claim.ai_analysis_completed_at,
        ai_analysis_error=claim.ai_analysis_error,
        stages=stage_outs,
        decision=decision,
        recommendation=rec,
        confidence=conf,
        validation_status=val_status,
        requires_human_review=req_review,
    )


def _trigger_analysis(db: Session, claim: Claim, actor: str):
    # Idempotency: if RUNNING, reject (via orchestrator's execution check as well)
    current = (claim.ai_analysis_status or "PENDING").upper()
    if current == "RUNNING":
        raise HTTPException(status_code=409, detail="AI analysis already running for this claim.")

    # Part 2.4: Create AIExecution via orchestrator (QUEUED → RUNNING)
    from app.services.ai_orchestrator import create_execution
    execution = create_execution(db, claim)
    # Also set claim to RUNNING for backwards compat (frontend still reads claim.ai_analysis_status)
    claim.ai_analysis_status = "RUNNING"
    claim.ai_analysis_requested_at = execution.requested_at
    claim.ai_analysis_error = None
    # Timeline AI_ANALYSIS_STARTED with execution_id
    db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_STARTED", actor=actor, notes="AI analysis started", event_metadata={"trigger": "api", "execution_id": execution.execution_id, "provider": execution.provider, "pipeline_version": execution.pipeline_version}))
    db.commit()
    return execution


@router.post("/api/claims/{claim_id}/analyze", response_model=AIAnalyzeStartResponse, status_code=202)
def analyze_claim_customer(
    claim_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_404(db, claim_id)
    _verify_customer_access(claim, current_user, db)
    execution = _trigger_analysis(db, claim, actor=f"customer:{current_user.email}")

    # Background execution via orchestrator (provider-agnostic, no sleep)
    from app.services.ai_orchestrator import execute_claim_analysis
    background_tasks.add_task(execute_claim_analysis, claim.id, execution.execution_id)

    return AIAnalyzeStartResponse(claim_id=claim.id, status=AIAnalysisStatus.RUNNING, message="AI analysis started")


@router.get("/api/claims/{claim_id}/analysis", response_model=AIAnalysisResponse)
def get_analysis_customer(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = _get_claim_or_404(db, claim_id)
    _verify_customer_access(claim, current_user, db)
    # This endpoint MUST NOT invoke AI
    return _build_analysis_response(db, claim)


@router.post("/api/admin/claims/{claim_id}/analyze", response_model=AIAnalyzeStartResponse, status_code=202)
def analyze_claim_admin(
    claim_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    claim = _get_claim_or_404(db, claim_id)
    execution = _trigger_analysis(db, claim, actor=f"admin:{current_user.email}")
    from app.services.ai_orchestrator import execute_claim_analysis
    background_tasks.add_task(execute_claim_analysis, claim.id, execution.execution_id)
    return AIAnalyzeStartResponse(claim_id=claim.id, status=AIAnalysisStatus.RUNNING, message="AI analysis started (admin)")


@router.get("/api/admin/claims/{claim_id}/analysis", response_model=AIAnalysisResponse)
def get_analysis_admin(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    claim = _get_claim_or_404(db, claim_id)
    return _build_analysis_response(db, claim)


@router.get("/api/admin/claims/{claim_id}/ai-executions")
def get_executions_admin(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "support")),
):
    from app.models.claim import AIExecution
    claim = _get_claim_or_404(db, claim_id)
    execs = db.query(AIExecution).filter(AIExecution.claim_id == claim_id).order_by(AIExecution.created_at.desc()).all()
    # Sanitize: only safe fields
    return {
        "claim_id": claim.id,
        "executions": [
            {
                "execution_id": e.execution_id,
                "status": e.status,
                "provider": e.provider,
                "model": e.model,
                "pipeline_version": e.pipeline_version,
                "attempt": e.attempt,
                "duration_ms": e.duration_ms,
                "requested_at": e.requested_at.isoformat() if e.requested_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "error_code": e.error_code,
                "error_message": e.error_message,
            }
            for e in execs
        ],
    }
