"""
AI Service — Part 2.1 offline foundation
Uses ONLY existing MockRocketRideClient, no vendor calls.
Background-safe session handling, deterministic validation, safe logging.
"""

import logging
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# Ensure warrantyos/ is on path for rocketrider import (sibling to backend)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.claim import Claim, ClaimAnalysis, ClaimDecision, ClaimTimeline
from app.models.product import Product, ProductSerial, WarrantyPolicy
from app.models.user import Customer
from rocketrider.adapter import MockRocketRideClient
from rocketrider.pipeline import ClaimPipelineInput, STAGES
from app.services.ai_validator import validate_pipeline_result

logger = logging.getLogger("warrantyos.ai")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [ai] claim=%(claim_id)s code=%(claim_code)s status=%(status)s dur=%(duration)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _build_pipeline_input(db: Session, claim: Claim) -> ClaimPipelineInput:
    product = db.query(Product).filter(Product.id == claim.product_id).first()
    serial = db.query(ProductSerial).filter(ProductSerial.id == claim.serial_id).first() if claim.serial_id else None
    policy = db.query(WarrantyPolicy).filter(WarrantyPolicy.product_id == claim.product_id).first() if product else None

    # Evidence flags (never send file paths)
    from app.models.claim import ClaimEvidence
    evidences = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
    has_invoice = any(e.evidence_type == "INVOICE" for e in evidences)
    has_photo = any(e.evidence_type == "PHOTO" for e in evidences)
    has_video = any(e.evidence_type == "VIDEO" for e in evidences)

    # customer_claim_count_90d
    since = datetime.now(timezone.utc) - timedelta(days=90)
    try:
        count_90d = db.query(Claim).filter(Claim.customer_id == claim.customer_id, Claim.created_at >= since).count()
    except Exception:
        count_90d = 0

    return ClaimPipelineInput(
        claim_code=claim.claim_code,
        product_name=product.name if product else "Unknown",
        category=product.category if product else "Unknown",
        serial_number=serial.serial_number if serial else "",
        fault_description=claim.fault_description or "",
        purchase_date=claim.purchase_date.isoformat() if claim.purchase_date else None,
        warranty_months=policy.warranty_months if policy else (product.warranty_period_months if product else 12),
        covered=policy.covered or [] if policy else [],
        not_covered=policy.not_covered or [] if policy else [],
        has_invoice=has_invoice,
        has_photo=has_photo,
        has_video=has_video,
        customer_claim_count_90d=count_90d,
    )


def analyze_claim(claim_id: int):
    """
    Background-safe AI analysis for a single claim.
    Creates new Session, loads claim, runs MockRocketRideClient, validates, persists.
    Never modifies claims.warranty_eligible / eligibility_reason / warranty_checked_at.
    On failure, sets ai_analysis_status=FAILED and creates AI_ANALYSIS_FAILED timeline.
    """
    start = time.monotonic()
    db: Session = SessionLocal()
    claim_code = f"id={claim_id}"
    status = "UNKNOWN"
    try:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            logger.warning("claim not found", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        claim_code = claim.claim_code
        # Part 2.4: No artificial sleep — RUNNING state is now the job lifecycle itself
        # The orchestrator's execution record provides the observable window
        # Ensure we are in RUNNING (set by API). If not, still proceed but log
        # Build input
        try:
            pipeline_input = _build_pipeline_input(db, claim)
        except Exception as e:
            # failure building input
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = "Failed to build AI input"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to build AI input", event_metadata={"error": "input_build_failed"}))
            db.commit()
            logger.error("input build failed", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # Build rich AI context (Part 2.2) — evidence, historical, policy, risk
        try:
            from app.services.ai_context_builder import build_ai_context
            ai_context = build_ai_context(db, claim)
            logger.info("AI_CONTEXT_BUILT", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "RUNNING", "duration": f"{time.monotonic()-start:.2f}s"})
            # Log counts (no PII) — use same logger with required extra
            logger.info(
                f"AI_CONTEXT_BUILT claim_id={claim.id} evidence_count={len(ai_context.evidence.items)} missing_count={len(ai_context.evidence.completeness.missing)} similar_cases={len(ai_context.similar_cases.top_cases)} policy_matches={len(ai_context.policy_context)} risk_signals={len(ai_context.risk_signals)}",
                extra={"claim_id": claim_id, "claim_code": claim_code, "status": "RUNNING", "duration": f"{time.monotonic()-start:.2f}s"},
            )
        except Exception as e:
            # Context build failure should not fail entire analysis; fall back to basic
            ai_context = None
            logger.error("context build failed", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})

        # Call MockRocketRideClient (deterministic, offline) — now with enriched context
        try:
            client = MockRocketRideClient()
            result = client.run_pipeline(pipeline_input)

            # Enrich stage outputs with real intelligence (Part 2.2)
            if ai_context:
                # DOCUMENT_EXTRACTION: add extracted_fields, evidence_items, quality, missing
                if "DOCUMENT_EXTRACTION" in result.stage_outputs:
                    doc_out = result.stage_outputs["DOCUMENT_EXTRACTION"]
                    # Add structured fields from evidence intelligence (mode='json' for date serialization)
                    doc_out["extracted_fields"] = ai_context.evidence.extracted_document.model_dump(mode='json') if ai_context.evidence.extracted_document else {}
                    doc_out["evidence_items"] = [item.model_dump(mode='json') for item in ai_context.evidence.items]
                    doc_out["evidence_quality"] = ai_context.evidence.completeness.overall
                    doc_out["missing_information"] = ai_context.evidence.completeness.missing
                    result.stage_outputs["DOCUMENT_EXTRACTION"] = doc_out

                # POLICY_CHECK -> POLICY_INTERPRETATION (keep both for backward compat)
                if "POLICY_CHECK" in result.stage_outputs:
                    policy_out = result.stage_outputs["POLICY_CHECK"]
                    policy_out["matched_policies"] = [p.model_dump(mode='json') for p in ai_context.policy_context]
                    policy_out["policy_relevance"] = {p.title: p.relevance for p in ai_context.policy_context}
                    policy_out["policy_context"] = f"{len(ai_context.policy_context)} relevant policy items retrieved"
                    result.stage_outputs["POLICY_CHECK"] = policy_out
                    # Also add POLICY_INTERPRETATION alias
                    result.stage_outputs["POLICY_INTERPRETATION"] = policy_out

                # EVIDENCE_ANALYSIS: add evidence completeness
                if "EVIDENCE_ANALYSIS" in result.stage_outputs:
                    ev_out = result.stage_outputs["EVIDENCE_ANALYSIS"]
                    ev_out["evidence_completeness"] = ai_context.evidence.completeness.model_dump(mode='json')
                    ev_out["normalized_evidence"] = [i.model_dump(mode='json') for i in ai_context.evidence.items]
                    result.stage_outputs["EVIDENCE_ANALYSIS"] = ev_out

                # SIMILAR_CASE_SEARCH: enrich with real historical cases
                if "SIMILAR_CASE_SEARCH" in result.stage_outputs:
                    sim_out = result.stage_outputs["SIMILAR_CASE_SEARCH"]
                    sim_out["similar_case_count"] = ai_context.similar_cases.similar_case_count
                    sim_out["top_cases"] = [c.model_dump(mode='json') for c in ai_context.similar_cases.top_cases]
                    sim_out["similarity_scores"] = {c.case_id: c.similarity_score for c in ai_context.similar_cases.top_cases}
                    sim_out["matched_features"] = {c.case_id: c.matched_features for c in ai_context.similar_cases.top_cases}
                    result.stage_outputs["SIMILAR_CASE_SEARCH"] = sim_out
                    # Alias for spec
                    result.stage_outputs["SIMILAR_CASES"] = sim_out

                # RISK_ASSESSMENT / FRAUD_RISK: add risk signals
                risk_out = {
                    "risk_signals": [r.model_dump(mode='json') for r in ai_context.risk_signals],
                    "risk_level": "HIGH" if any(r.severity == "HIGH" for r in ai_context.risk_signals) else "MEDIUM" if ai_context.risk_signals else "LOW",
                    "explanations": [r.description for r in ai_context.risk_signals],
                }
                result.stage_outputs["RISK_ASSESSMENT"] = risk_out
                result.stage_outputs["FRAUD_RISK"] = risk_out  # backward compat

                # DECISION_AGENT: enrich with reasoning factors
                if "DECISION_AGENT" in result.stage_outputs:
                    dec_out = result.stage_outputs["DECISION_AGENT"]
                    dec_out["reasoning_factors"] = [
                        f"Warranty eligible: {claim.warranty_eligible}",
                        f"Evidence completeness: {ai_context.evidence.completeness.overall}",
                        f"Risk signals: {len(ai_context.risk_signals)}",
                        f"Similar cases: {ai_context.similar_cases.similar_case_count}",
                    ]
                    dec_out["supporting_evidence"] = result.evidence
                    dec_out["contradicting_evidence"] = []
                    # Adjust recommendation based on real context (deterministic)
                    # If evidence incomplete, force MORE_INFORMATION_REQUIRED
                    if ai_context.evidence.completeness.overall == "INCOMPLETE":
                        # Only override if mock said REPAIR/REPLACE but evidence incomplete
                        if result.recommendation in ["REPAIR", "REPLACE"]:
                            result.recommendation = "MORE_INFORMATION_REQUIRED"
                            result.confidence = min(result.confidence, 0.55)
                            dec_out["recommendation"] = result.recommendation
                            dec_out["confidence"] = result.confidence
                    # If high risk, force HUMAN_REVIEW
                    if any(r.severity == "HIGH" for r in ai_context.risk_signals):
                        if result.recommendation not in ["HUMAN_REVIEW", "DENY"]:
                            result.recommendation = "HUMAN_REVIEW"
                            result.risk_flags.append("High risk pattern requires human review")
                            dec_out["recommendation"] = result.recommendation
                    result.stage_outputs["DECISION_AGENT"] = dec_out
                    result.stage_outputs["RECOMMENDATION"] = dec_out

                # Update result's risk_flags and missing_information from real context
                # Merge mock's flags with real risk signals
                for rs in ai_context.risk_signals:
                    if rs.code not in result.risk_flags and rs.description not in result.risk_flags:
                        result.risk_flags.append(rs.code)
                for miss in ai_context.evidence.completeness.missing:
                    if miss not in result.missing_information:
                        # Map evidence types to human-readable missing
                        msg = f"{miss} not provided" if "not provided" not in miss else miss
                        if msg not in result.missing_information:
                            result.missing_information.append(msg)

        except Exception as e:
            # adapter exception
            sanitized = "AI adapter error"
            claim.ai_analysis_status = "FAILED"
            claim.ai_analysis_error = sanitized
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes=sanitized, event_metadata={"error": sanitized}))
            db.commit()
            logger.error("adapter exception", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

        # Validate deterministically
        try:
            validation_status, validation_errors, requires_review, review_reason = validate_pipeline_result(result)
            # Also consider risk signals from context for human review
            if ai_context and ai_context.risk_signals:
                for rs in ai_context.risk_signals:
                    if rs.severity == "HIGH" and not requires_review:
                        requires_review = True
                        review_reason = f"High risk: {rs.code} - {rs.description}"
        except Exception as e:
            validation_status = "INVALID"
            validation_errors = [{"field": "validator", "error": "validator exception"}]
            requires_review = True
            review_reason = "Validator exception"

        # Part 2.3: Decision Governance (confidence bands, conflicts, explanation, scorecard)
        governance_result = None
        try:
            from app.services.decision_governance import evaluate_governance
            # Build a temporary ClaimDecision-like object for governance input
            # Use the validated result plus context
            temp_decision = type('TmpDecision', (), {
                'recommendation': result.recommendation,
                'confidence': float(result.confidence) if result.confidence is not None else 0.0,
                'validation_status': validation_status,
                'evidence': result.evidence or [],
                'risk_flags': result.risk_flags or [],
                'missing_information': result.missing_information or [],
            })()
            # Need a ClaimDecision-like for governance; we can pass a dict-like, but governance expects ClaimDecision
            # Instead, create a real ClaimDecision instance without persisting yet
            draft_decision = ClaimDecision(
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
            governance_result = evaluate_governance(db, claim, draft_decision, ai_context) if ai_context else None
            if governance_result:
                # Override requires_review with governance result (more comprehensive)
                requires_review = governance_result.requires_human_review or requires_review
                # Use governance review reasons if more detailed
                if governance_result.review_reasons:
                    review_reason = "; ".join(governance_result.review_reasons)
        except Exception as e:
            # Governance failure should not fail entire analysis; log and continue
            governance_result = None
            logger.error("governance failed", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})

        # Persist one ClaimAnalysis per stage (clean old stages for this claim to keep only latest 6)
        try:
            # Remove previous analysis rows for this claim to keep only latest run (hackathon simple)
            db.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).delete()
            for stage in STAGES:
                stage_result = result.stage_outputs.get(stage)
                if stage_result is None:
                    # If stage missing, store empty dict but will be flagged as INVALID already
                    stage_result = {}
                db.add(ClaimAnalysis(claim_id=claim.id, stage=stage, result=stage_result))

            # Persist ClaimDecision for this run (with governance)
            # Determine version
            existing_count = db.query(ClaimDecision).filter(ClaimDecision.claim_id == claim.id).count()
            decision_version = existing_count + 1
            # Extract governance fields if available
            gov_score = None
            gov_band = None
            gov_conflicts = None
            gov_explanation = None
            if governance_result:
                gov_score = governance_result.decision_score
                gov_band = governance_result.confidence_band.value if hasattr(governance_result.confidence_band, 'value') else str(governance_result.confidence_band)
                gov_conflicts = [c.model_dump(mode='json') for c in governance_result.conflicts] if governance_result.conflicts else None
                gov_explanation = governance_result.explanation.model_dump(mode='json') if governance_result.explanation else None
                # Also update requires_review/review_reason from governance if more detailed
                # (already merged above)

            decision = ClaimDecision(
                claim_id=claim.id,
                recommendation=result.recommendation,
                confidence=float(result.confidence) if result.confidence is not None else 0.0,
                evidence=result.evidence or [],
                risk_flags=result.risk_flags or [],
                missing_information=result.missing_information or [],
                requires_human_review=requires_review,
                review_reason=review_reason[:255] if review_reason else None,
                final_outcome=None,  # never auto-set
                model="mock",
                validation_status=validation_status,
                validation_errors=validation_errors if validation_errors else None,
                decision_version=decision_version,
                decision_score=gov_score,
                confidence_band=gov_band,
                conflicts=gov_conflicts,
                explanation=gov_explanation,
            )
            db.add(decision)

            # Update claim AI status
            claim.ai_analysis_status = "COMPLETED"
            claim.ai_analysis_completed_at = datetime.now(timezone.utc)
            claim.ai_analysis_error = None

            # Timeline events
            db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_COMPLETED", actor="system", notes=f"AI analysis completed: {result.recommendation} ({result.confidence})", event_metadata={"recommendation": result.recommendation, "confidence": result.confidence, "validation_status": validation_status}))

            if validation_status == "INVALID":
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_VALIDATION_FAILED", actor="system", notes="AI validation failed", event_metadata={"errors": validation_errors}))
            if requires_review:
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_HUMAN_REVIEW_REQUIRED", actor="system", notes=review_reason, event_metadata={"reason": review_reason, "risk_flags": result.risk_flags}))

            db.commit()
            status = "COMPLETED"
            logger.info("ai completed", extra={"claim_id": claim_id, "claim_code": claim_code, "status": status, "duration": f"{time.monotonic()-start:.2f}s"})
        except Exception as e:
            db.rollback()
            # Try to mark failed with new session? We are in same session, try again
            try:
                claim = db.query(Claim).filter(Claim.id == claim_id).first()
                if claim:
                    claim.ai_analysis_status = "FAILED"
                    claim.ai_analysis_error = "Failed to persist AI result"
                    claim.ai_analysis_completed_at = datetime.now(timezone.utc)
                    db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Failed to persist AI result", event_metadata={"error": "persist_failed"}))
                    db.commit()
            except Exception:
                pass
            logger.error("persist failed", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
            return

    except Exception as e:
        # Top-level catch: ensure we don't crash background task silently
        try:
            db.rollback()
            claim = db.query(Claim).filter(Claim.id == claim_id).first()
            if claim:
                claim.ai_analysis_status = "FAILED"
                claim.ai_analysis_error = "Unexpected AI failure"
                claim.ai_analysis_completed_at = datetime.now(timezone.utc)
                db.add(ClaimTimeline(claim_id=claim.id, event_type="AI_ANALYSIS_FAILED", actor="system", notes="Unexpected AI failure", event_metadata={"error": "unexpected"}))
                db.commit()
        except Exception:
            pass
        logger.error("unexpected", extra={"claim_id": claim_id, "claim_code": claim_code, "status": "FAILED", "duration": f"{time.monotonic()-start:.2f}s"})
    finally:
        try:
            db.close()
        except Exception:
            pass
