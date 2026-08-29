"""
AI Orchestrator — Part 2.4
Coordinates: context → provider → validation → governance → persistence.
Provider-agnostic, offline, deterministic, no external calls.
"""

import logging
import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.claim import Claim, ClaimAnalysis, ClaimDecision, ClaimTimeline, AIExecution
from app.schemas.ai_execution import AIExecutionContext
from app.services.ai_provider_registry import get_provider

logger = logging.getLogger("warrantyos.orchestrator")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [orchestrator] execution_id=%(execution_id)s claim_id=%(claim_id)s status=%(status)s dur=%(duration)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Error codes
ERROR_CODES = {
    "AI_EXECUTION_FAILED": "AI_EXECUTION_FAILED",
    "AI_EXECUTION_TIMEOUT": "AI_EXECUTION_TIMEOUT",
    "AI_PROVIDER_UNAVAILABLE": "AI_PROVIDER_UNAVAILABLE",
    "AI_VALIDATION_FAILED": "AI_VALIDATION_FAILED",
    "AI_EXECUTION_ALREADY_RUNNING": "AI_EXECUTION_ALREADY_RUNNING",
}


def _generate_execution_id(claim_id: int) -> str:
    # UUID-based, safe, no PII
    return f"AI-{claim_id}-{uuid.uuid4().hex[:8].upper()}"


def create_execution(db: Session, claim: Claim, attempt: int = 1) -> AIExecution:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exec_id = _generate_execution_id(claim.id)
    execution = AIExecution(
        execution_id=exec_id,
        claim_id=claim.id,
        status="QUEUED",
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL,
        pipeline_version=settings.AI_PIPELINE_VERSION,
        attempt=attempt,
        requested_at=now,
        started_at=None,
        completed_at=None,
        duration_ms=None,
        error_code=None,
        error_message=None,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _update_execution_status(db: Session, execution: AIExecution, status: str, error_code: Optional[str] = None, error_message: Optional[str] = None):
    execution.status = status
    if status == "RUNNING" and not execution.started_at:
        execution.started_at = datetime.now(timezone.utc)
    if status in ("COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED"):
        execution.completed_at = datetime.now(timezone.utc)
        if execution.started_at and execution.completed_at:
            try:
                start = execution.started_at
                end = execution.completed_at
                # Handle SQLite naive vs aware
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                execution.duration_ms = int((end - start).total_seconds() * 1000)
            except Exception:
                execution.duration_ms = None
    if error_code:
        execution.error_code = error_code
    if error_message:
        # Sanitize: no PII, no stack trace
        execution.error_message = error_message[:500]
    db.commit()


def execute_claim_analysis(claim_id: int, execution_id: str):
    """
    Main orchestrator entry. Called via BackgroundTasks.
    Handles: context → provider → validate → govern → persist → timeline → execution lifecycle.
    Never modifies warranty_eligible.
    """
    start = time.monotonic()
    db: Session = SessionLocal()
    execution: Optional[AIExecution] = None
    claim_code = f"id={claim_id}"
    try:
        # Load execution
        execution = db.query(AIExecution).filter(AIExecution.execution_id == execution_id).first()
        if not execution:
            logger.error("execution not found", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Claim not found")
            return

        claim_code = claim.claim_code
        # Update to RUNNING
        _update_execution_status(db, execution, "RUNNING")
        logger.info("execution started", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "RUNNING", "duration": f"{time.monotonic()-start:.2f}s"})

        # Timeout handling: we will enforce overall timeout via config
        settings = get_settings()
        timeout = settings.AI_EXECUTION_TIMEOUT_SECONDS

        # Use a try with timeout simulation (since Mock is fast, we won't actually timeout, but we check duration)
        # For Part 2.4, we implement simple timeout check after provider call

        # 1. Build context (evidence, historical, policy, risk)
        from app.services.ai_context_builder import build_ai_context
        try:
            context = build_ai_context(db, claim)
        except Exception as e:
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Failed to build AI context")
            # Also update claim
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "Failed to build AI context"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to build AI context", event_metadata={"execution_id": execution_id, "error": "context_failed"}))
            db.commit()
            logger.error("context build failed", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # 2. Build pipeline input
        from app.services.ai_service import _build_pipeline_input
        try:
            pipeline_input = _build_pipeline_input(db, claim)
        except Exception as e:
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Failed to build pipeline input")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "Failed to build pipeline input"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to build pipeline input", event_metadata={"execution_id": execution_id}))
            db.commit()
            logger.error("pipeline input failed", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # 3. Select provider
        try:
            provider = get_provider()
        except Exception as e:
            _update_execution_status(db, execution, "FAILED", "AI_PROVIDER_UNAVAILABLE", "Provider unavailable")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI provider unavailable"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Provider unavailable", event_metadata={"execution_id": execution_id}))
            db.commit()
            logger.error("provider unavailable", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # 4. Build execution context
        exec_ctx = AIExecutionContext(
            execution_id=execution_id,
            claim_id=claim.id,
            claim_code=claim.claim_code,
            provider=execution.provider,
            model=execution.model,
            pipeline_version=execution.pipeline_version,
            requested_at=execution.requested_at,
            started_at=execution.started_at or datetime.now(timezone.utc),
            attempt=execution.attempt,
            timeout_seconds=timeout,
            status="RUNNING"
        )

        # 5. Execute provider with timeout protection
        # For offline mock, we don't need real timeout, but we implement check
        provider_start = time.monotonic()
        try:
            # Check if already exceeded timeout before call
            if time.monotonic() - start > timeout:
                raise TimeoutError("AI execution timed out before provider call")
            result = provider.run_pipeline(pipeline_input, context, exec_ctx)
            # Check timeout after call
            if time.monotonic() - start > timeout:
                raise TimeoutError("AI execution timed out after provider")
        except TimeoutError as e:
            _update_execution_status(db, execution, "TIMED_OUT", "AI_EXECUTION_TIMEOUT", "AI execution timed out")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI execution timed out"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="AI execution timed out", event_metadata={"execution_id": execution_id, "error": "timeout"}))
            db.commit()
            logger.error("timeout", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "TIMED_OUT", "duration": f"{time.monotonic()-start:.2f}s"})
            return
        except Exception as e:
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Provider failed")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI provider failed"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Provider failed", event_metadata={"execution_id": execution_id, "error": "provider_failed"}))
            db.commit()
            logger.error("provider failed", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # 6. Validate
        from app.services.ai_validator import validate_pipeline_result
        try:
            _update_execution_status(db, execution, "VALIDATING")
            validation_status, validation_errors, requires_review, review_reason = validate_pipeline_result(result)
            # Also consider risk from context
            if context and context.risk_signals:
                for rs in context.risk_signals:
                    if rs.severity == "HIGH" and not requires_review:
                        requires_review = True
                        review_reason = f"High risk: {rs.code}"
        except Exception as e:
            validation_status = "INVALID"
            validation_errors = [{"field": "validator", "error": "validator exception"}]
            requires_review = True
            review_reason = "Validator exception"

        # 7. Governance
        governance_result = None
        try:
            _update_execution_status(db, execution, "GOVERNING")
            from app.services.decision_governance import evaluate_governance
            from app.models.claim import ClaimDecision
            draft = ClaimDecision(
                claim_id=claim.id,
                recommendation=result.recommendation,
                confidence=float(result.confidence) if result.confidence is not None else 0.0,
                evidence=result.evidence or [],
                risk_flags=result.risk_flags or [],
                missing_information=result.missing_information or [],
                requires_human_review=requires_review,
                review_reason=review_reason[:255] if review_reason else None,
                validation_status=validation_status,
                validation_errors=validation_errors if validation_errors else None,
            )
            governance_result = evaluate_governance(db, claim, draft, context) if context else None
            if governance_result:
                requires_review = governance_result.requires_human_review or requires_review
                if governance_result.review_reasons:
                    review_reason = "; ".join(governance_result.review_reasons)
        except Exception as e:
            governance_result = None
            logger.error(f"governance failed: {e} {traceback.format_exc()}", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})

        # 8. Persist stages + decision (reuse logic from ai_service, but now via orchestrator)
        # We need to handle stage enrichment already done in ai_service's Mock path? For orchestrator, we should enrich similarly
        # For now, we will reuse the enrichment logic from ai_service: the result already has enriched stage_outputs from context if we called via ai_context
        # But our provider call was with context, and Mock already handled basic, but we need to enrich as ai_service does
        # Let's enrich here similarly to ai_service
        try:
            # Enrich if context exists (duplicate of ai_service enrichment, but we do it here for orchestrator path)
            if context:
                # DOCUMENT_EXTRACTION
                if "DOCUMENT_EXTRACTION" in result.stage_outputs:
                    doc_out = result.stage_outputs["DOCUMENT_EXTRACTION"]
                    doc_out["extracted_fields"] = context.evidence.extracted_document.model_dump(mode='json') if context.evidence.extracted_document else {}
                    doc_out["evidence_items"] = [item.model_dump(mode='json') for item in context.evidence.items]
                    doc_out["evidence_quality"] = context.evidence.completeness.overall
                    doc_out["missing_information"] = context.evidence.completeness.missing
                if "POLICY_CHECK" in result.stage_outputs:
                    policy_out = result.stage_outputs["POLICY_CHECK"]
                    policy_out["matched_policies"] = [p.model_dump(mode='json') for p in context.policy_context]
                    policy_out["policy_relevance"] = {p.title: p.relevance for p in context.policy_context}
                if "EVIDENCE_ANALYSIS" in result.stage_outputs:
                    ev_out = result.stage_outputs["EVIDENCE_ANALYSIS"]
                    ev_out["evidence_completeness"] = context.evidence.completeness.model_dump(mode='json')
                if "SIMILAR_CASE_SEARCH" in result.stage_outputs:
                    sim_out = result.stage_outputs["SIMILAR_CASE_SEARCH"]
                    sim_out["similar_case_count"] = context.similar_cases.similar_case_count
                    sim_out["top_cases"] = [c.model_dump(mode='json') for c in context.similar_cases.top_cases]
                # Risk already handled via governance
        except Exception:
            pass

        # 9. Persist
        try:
            from app.models.claim import ClaimAnalysis, ClaimDecision, ClaimTimeline
            from rocketrider.pipeline import STAGES
            # Clean old analysis (keep latest 6)
            db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).delete()
            for stage in STAGES:
                stage_result = result.stage_outputs.get(stage, {})
                db.add(ClaimAnalysis(claim_id=claim.id, stage=stage, result=stage_result))
            # Also persist enriched aliases for observability
            for alias in ["POLICY_INTERPRETATION", "SIMILAR_CASES", "RISK_ASSESSMENT", "FRAUD_RISK", "RECOMMENDATION"]:
                if alias in result.stage_outputs:
                    db.add(ClaimAnalysis(claim_id=claim.id, stage=alias, result=result.stage_outputs[alias]))

            # Determine version
            existing_count = db.query(ClaimDecision).filter(ClaimDecision.claim_id == claim.id).count()
            version = existing_count + 1
            gov_score = None
            gov_band = None
            gov_conflicts = None
            gov_explanation = None
            if governance_result:
                gov_score = governance_result.decision_score
                gov_band = governance_result.confidence_band.value if hasattr(governance_result.confidence_band, 'value') else str(governance_result.confidence_band)
                gov_conflicts = [c.model_dump(mode='json') for c in governance_result.conflicts] if governance_result.conflicts else None
                gov_explanation = governance_result.explanation.model_dump(mode='json') if governance_result.explanation else None

            decision = ClaimDecision(
                claim_id=claim.id,
                recommendation=result.recommendation,
                confidence=float(result.confidence) if result.confidence is not None else 0.0,
                evidence=result.evidence or [],
                risk_flags=result.risk_flags or [],
                missing_information=result.missing_information or [],
                requires_human_review=requires_review,
                review_reason=review_reason[:255] if review_reason else None,
                final_outcome=None,
                model=execution.model,
                validation_status=validation_status,
                validation_errors=validation_errors if validation_errors else None,
                decision_version=version,
                decision_score=gov_score,
                confidence_band=gov_band,
                conflicts=gov_conflicts,
                explanation=gov_explanation,
            )
            db.add(decision)
            # Update claim
            claim.ai_analysis_status = "COMPLETED"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            claim.ai_analysis_error = None
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_COMPLETED", actor="system", notes=f"AI analysis completed: {result.recommendation} ({result.confidence})", event_metadata={"execution_id": execution_id, "recommendation": result.recommendation, "confidence": result.confidence, "validation_status": validation_status, "pipeline_version": execution.pipeline_version}))
            if validation_status == "INVALID":
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_VALIDATION_FAILED", actor="system", notes="AI validation failed", event_metadata={"execution_id": execution_id, "errors": validation_errors}))
            if requires_review:
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_HUMAN_REVIEW_REQUIRED", actor="system", notes=review_reason, event_metadata={"execution_id": execution_id, "reason": review_reason}))
            # Complete execution
            _update_execution_status(db, execution, "COMPLETED")
            db.commit()
            logger.info("execution completed", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "COMPLETED", "duration": f"{time.monotonic()-start:.2f}s"})
        except Exception as e:
            db.rollback()
            logger.error(f"persist failed: {e} {traceback.format_exc()}", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            try:
                # Use a fresh session for error handling to avoid detached state
                from app.core.database import SessionLocal as FreshSession
                fresh_db = FreshSession()
                try:
                    fresh_exec = fresh_db.query(AIExecution).filter(AIExecution.execution_id == execution_id).first()
                    if fresh_exec:
                        fresh_exec.status = "FAILED"
                        fresh_exec.error_code = "AI_EXECUTION_FAILED"
                        fresh_exec.error_message = "Failed to persist"
                        fresh_exec.completed_at = datetime.now(timezone.utc)
                        if fresh_exec.started_at and fresh_exec.completed_at:
                            fresh_exec.duration_ms = int((fresh_exec.completed_at - fresh_exec.started_at).total_seconds() * 1000)
                    fresh_claim = fresh_db.query(Claim).filter(Claim.id == claim_id).first()
                    if fresh_claim:
                        fresh_claim.ai_analysis_status = "FAILED"
                        fresh_claim.ai_analysis_error = "Failed to persist AI result"
                        fresh_claim.ai_analysis_completed_at = datetime.now(timezone.utc)
                        fresh_db.add(ClaimTimeline(claim_id=fresh_claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to persist", event_metadata={"execution_id": execution_id}))
                    fresh_db.commit()
                finally:
                    fresh_db.close()
            except Exception as e2:
                logger.error(f"persist failed handling failed: {e2} {traceback.format_exc()}", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            from app.core.database import SessionLocal as FreshSession2
            fresh_db = FreshSession2()
            try:
                fresh_exec = fresh_db.query(AIExecution).filter(AIExecution.execution_id == execution_id).first()
                if fresh_exec:
                    fresh_exec.status = "FAILED"
                    fresh_exec.error_code = "AI_EXECUTION_FAILED"
                    fresh_exec.error_message = "Unexpected"
                    fresh_exec.completed_at = datetime.now(timezone.utc)
                    if fresh_exec.started_at and fresh_exec.completed_at:
                        fresh_exec.duration_ms = int((fresh_exec.completed_at - fresh_exec.started_at).total_seconds() * 1000)
                fresh_claim = fresh_db.query(Claim).filter(Claim.id == claim_id).first()
                if fresh_claim:
                    fresh_claim.ai_analysis_status = "FAILED"
                    fresh_claim.ai_analysis_error = "Unexpected AI failure"
                    fresh_claim.ai_analysis_completed_at = datetime.now(timezone.utc)
                    fresh_db.add(ClaimTimeline(claim_id=fresh_claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Unexpected", event_metadata={"execution_id": execution_id}))
                fresh_db.commit()
            finally:
                fresh_db.close()
        except Exception:
            pass
        logger.error(f"unexpected: {e} {traceback.format_exc()}", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
    finally:
        try:
            db.close()
        except Exception:
            pass
