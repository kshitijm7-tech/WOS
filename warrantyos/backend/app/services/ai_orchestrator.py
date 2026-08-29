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
from app.models.claim import Claim, ClaimAnalysis, ClaimDecision, ClaimTimeline, AIExecution, AIExecutionStage
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
        requested_provider=settings.AI_PROVIDER,
        actual_provider=settings.AI_PROVIDER,
        requested_model=settings.AI_MODEL,
        actual_model=settings.AI_MODEL,
        fallback_used=False,
        fallback_reason=None,
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
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                execution.duration_ms = int((end - start).total_seconds() * 1000)
                execution.latency_ms = execution.duration_ms
            except Exception:
                execution.duration_ms = None
    if error_code:
        execution.error_code = error_code
        execution.failure_class = error_code
    if error_message:
        execution.error_message = error_message[:500]
    db.commit()


def _record_stage_execution(
    db: Session,
    ai_execution_id: int,
    stage_name: str,
    status: str,
    start_time: float,
    end_time: float,
    provider_name: str,
    model_name: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata_json: Optional[dict] = None
):
    try:
        from app.models.claim import AIExecutionStage
        started_at = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time) * 1000)
        stage_row = AIExecutionStage(
            ai_execution_id=ai_execution_id,
            stage_name=stage_name,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=max(duration_ms, 1),
            error_code=error_code,
            error_message=error_message,
            provider=provider_name,
            model=model_name,
            metadata_json=metadata_json or {},
        )
        db.add(stage_row)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to record AIExecutionStage {stage_name}: {e}")


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
        execution = db.query(AIExecution).filter(AIExecution.execution_id == execution_id).first()
        if not execution:
            logger.error("execution not found", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Claim not found")
            return

        claim_code = claim.claim_code
        _update_execution_status(db, execution, "RUNNING")
        logger.info("execution started", extra={"execution_id": execution_id, "claim_id": claim_id, "status": "RUNNING", "duration": f"{time.monotonic()-start:.2f}s"})

        settings = get_settings()
        timeout = settings.AI_EXECUTION_TIMEOUT_SECONDS

        # 1. Build context & Stage 1: DOCUMENT_EXTRACTION
        stage_start = time.monotonic()
        from app.services.ai_context_builder import build_ai_context
        try:
            context = build_ai_context(db, claim)
            _record_stage_execution(
                db, execution.id, "DOCUMENT_EXTRACTION", "COMPLETED", stage_start, time.monotonic(),
                settings.AI_PROVIDER, settings.AI_MODEL, metadata_json={"doc_confidence": context.evidence.extracted_document.extraction_confidence if context.evidence.extracted_document else 0.0}
            )
        except Exception as e:
            _record_stage_execution(db, execution.id, "DOCUMENT_EXTRACTION", "FAILED", stage_start, time.monotonic(), settings.AI_PROVIDER, settings.AI_MODEL, error_code="CONTEXT_BUILD_FAILED", error_message=str(e))
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Failed to build AI context")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "Failed to build AI context"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to build AI context", event_metadata={"execution_id": execution_id, "error": "context_failed"}))
            db.commit()
            return

        # 2. Build pipeline input & Stage 2: POLICY_CHECK
        stage_start = time.monotonic()
        from app.services.ai_service import _build_pipeline_input
        try:
            pipeline_input = _build_pipeline_input(db, claim)
            _record_stage_execution(
                db, execution.id, "POLICY_CHECK", "COMPLETED", stage_start, time.monotonic(),
                settings.AI_PROVIDER, settings.AI_MODEL, metadata_json={"matched_policies_count": len(context.policy_context) if context else 0}
            )
        except Exception as e:
            _record_stage_execution(db, execution.id, "POLICY_CHECK", "FAILED", stage_start, time.monotonic(), settings.AI_PROVIDER, settings.AI_MODEL, error_code="PIPELINE_INPUT_FAILED", error_message=str(e))
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Failed to build pipeline input")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "Failed to build pipeline input"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to build pipeline input", event_metadata={"execution_id": execution_id}))
            db.commit()
            return

        # Record EVIDENCE_ANALYSIS & SIMILAR_CASE_SEARCH stages
        _record_stage_execution(db, execution.id, "EVIDENCE_ANALYSIS", "COMPLETED", time.monotonic()-0.01, time.monotonic(), settings.AI_PROVIDER, settings.AI_MODEL, metadata_json={"evidence_overall": context.evidence.completeness.overall if context else "UNKNOWN"})
        _record_stage_execution(db, execution.id, "SIMILAR_CASE_SEARCH", "COMPLETED", time.monotonic()-0.01, time.monotonic(), settings.AI_PROVIDER, settings.AI_MODEL, metadata_json={"similar_cases_count": context.similar_cases.similar_case_count if context else 0})

        # 3. Select provider & check Provider Truthfulness
        try:
            provider_inst = get_provider()
            actual_prov = getattr(provider_inst, "provider_name", "mock")
            actual_mod = getattr(provider_inst, "model_name", "mock-v1")
            requested_prov = settings.AI_PROVIDER.lower()
            requested_mod = settings.AI_MODEL

            fallback_used = False
            fallback_reason = None
            if requested_prov != "mock" and actual_prov == "mock":
                fallback_used = True
                fallback_reason = f"Provider {requested_prov} unavailable, fell back to mock"

            execution.requested_provider = requested_prov
            execution.actual_provider = actual_prov
            execution.requested_model = requested_mod
            execution.actual_model = actual_mod
            execution.provider = actual_prov
            execution.model = actual_mod
            execution.fallback_used = fallback_used
            execution.fallback_reason = fallback_reason
            db.commit()
        except Exception as e:
            _update_execution_status(db, execution, "FAILED", "AI_PROVIDER_UNAVAILABLE", "Provider unavailable")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI provider unavailable"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Provider unavailable", event_metadata={"execution_id": execution_id}))
            db.commit()
            return

        # 4. Build execution context
        exec_ctx = AIExecutionContext(
            execution_id=execution_id,
            claim_id=claim.id,
            claim_code=claim.claim_code,
            provider=execution.actual_provider or "mock",
            model=execution.actual_model or "mock-v1",
            pipeline_version=execution.pipeline_version,
            requested_at=execution.requested_at,
            started_at=execution.started_at or datetime.now(timezone.utc),
            attempt=execution.attempt,
            timeout_seconds=timeout,
            status="RUNNING"
        )

        # 5. Execute provider & Stage: DECISION_AGENT / RISK_ASSESSMENT
        stage_start = time.monotonic()
        try:
            if time.monotonic() - start > timeout:
                raise TimeoutError("AI execution timed out before provider call")
            result = provider_inst.run_pipeline(pipeline_input, context, exec_ctx)
            if time.monotonic() - start > timeout:
                raise TimeoutError("AI execution timed out after provider")

            _record_stage_execution(db, execution.id, "RISK_ASSESSMENT", "COMPLETED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, metadata_json={"risk_flags_count": len(result.risk_flags or [])})
            _record_stage_execution(db, execution.id, "DECISION_AGENT", "COMPLETED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, metadata_json={"recommendation": result.recommendation, "confidence": result.confidence})
        except TimeoutError as e:
            _record_stage_execution(db, execution.id, "DECISION_AGENT", "TIMED_OUT", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, error_code="AI_EXECUTION_TIMEOUT", error_message="Timed out")
            _update_execution_status(db, execution, "TIMED_OUT", "AI_EXECUTION_TIMEOUT", "AI execution timed out")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI execution timed out"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="AI execution timed out", event_metadata={"execution_id": execution_id, "error": "timeout"}))
            db.commit()
            return
        except Exception as e:
            _record_stage_execution(db, execution.id, "DECISION_AGENT", "FAILED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, error_code="PROVIDER_FAILED", error_message=str(e))
            _update_execution_status(db, execution, "FAILED", "AI_EXECUTION_FAILED", "Provider failed")
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "AI provider failed"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Provider failed", event_metadata={"execution_id": execution_id, "error": "provider_failed"}))
            db.commit()
            return

        # 6. Validate & Stage: VALIDATOR
        stage_start = time.monotonic()
        from app.services.ai_validator import validate_pipeline_result
        try:
            _update_execution_status(db, execution, "VALIDATING")
            validation_status, validation_errors, requires_review, review_reason = validate_pipeline_result(result)
            if context and context.risk_signals:
                for rs in context.risk_signals:
                    if rs.severity == "HIGH" and not requires_review:
                        requires_review = True
                        review_reason = f"High risk: {rs.code}"
            _record_stage_execution(db, execution.id, "VALIDATOR", "COMPLETED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, metadata_json={"validation_status": validation_status})
        except Exception as e:
            validation_status = "INVALID"
            validation_errors = [{"field": "validator", "error": "validator exception"}]
            requires_review = True
            review_reason = "Validator exception"
            _record_stage_execution(db, execution.id, "VALIDATOR", "FAILED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, error_code="VALIDATOR_FAILED", error_message=str(e))

        # 7. Governance & Stage: GOVERNANCE
        stage_start = time.monotonic()
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
            _record_stage_execution(db, execution.id, "GOVERNANCE", "COMPLETED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, metadata_json={"governance_score": float(governance_result.decision_score) if governance_result and governance_result.decision_score else None})
        except Exception as e:
            governance_result = None
            _record_stage_execution(db, execution.id, "GOVERNANCE", "FAILED", stage_start, time.monotonic(), execution.actual_provider, execution.actual_model, error_code="GOVERNANCE_FAILED", error_message=str(e))

        # 8. Enrich result stage outputs
        try:
            if context:
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
        except Exception:
            pass

        # 9. Persist decision + telemetry
        try:
            from rocketrider.pipeline import STAGES
            db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).delete()

            for stage in STAGES:
                stage_result = result.stage_outputs.get(stage, {})
                db.add(ClaimAnalysis(claim_id=claim.id, stage=stage, result=stage_result))
            for alias in ["POLICY_INTERPRETATION", "SIMILAR_CASES", "RISK_ASSESSMENT", "FRAUD_RISK", "RECOMMENDATION"]:
                if alias in result.stage_outputs:
                    db.add(ClaimAnalysis(claim_id=claim.id, stage=alias, result=result.stage_outputs[alias]))

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

            # Telemetry estimates
            execution.input_token_count = 450
            execution.output_token_count = 180
            execution.estimated_cost = 0.0  # Mock cost 0
            execution.provider_status = "COMPLETED"

            claim.ai_analysis_status = "COMPLETED"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            claim.ai_analysis_error = None
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_COMPLETED", actor="system", notes=f"AI analysis completed: {result.recommendation} ({result.confidence})", event_metadata={"execution_id": execution_id, "recommendation": result.recommendation, "confidence": result.confidence, "validation_status": validation_status, "pipeline_version": execution.pipeline_version, "fallback_used": execution.fallback_used}))
            if validation_status == "INVALID":
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_VALIDATION_FAILED", actor="system", notes="AI validation failed", event_metadata={"execution_id": execution_id, "errors": validation_errors}))
            if requires_review:
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_HUMAN_REVIEW_REQUIRED", actor="system", notes=review_reason, event_metadata={"execution_id": execution_id, "reason": review_reason}))
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
