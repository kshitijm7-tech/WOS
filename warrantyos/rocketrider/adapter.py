"""
RocketRideClient — the ONLY interface the rest of WarrantyOS is allowed to depend on for
AI-heavy claim analysis. See README.md in this folder for why, and where to connect the
real RocketRide SDK once it's available.

Part 2.4: MockRocketRideClient now also implements AIProvider (provider-agnostic).
"""

from abc import ABC, abstractmethod
import hashlib
import random
import sys
from pathlib import Path

# Ensure backend is importable for AIProvider when running mock standalone
try:
    from app.services.ai_provider import AIProvider  # type: ignore
except Exception:
    # Fallback import via path insertion (when running from rocketrider directly)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    try:
        from app.services.ai_provider import AIProvider  # type: ignore
    except Exception:
        # Define minimal fallback for type checking
        class AIProvider(ABC):  # type: ignore
            pass

from rocketrider.pipeline import ClaimPipelineInput, ClaimPipelineResult


class RocketRideClient(ABC):
    """Abstract contract. Every stage returns a dict that gets stored in claim_analysis."""

    @abstractmethod
    def run_pipeline(self, data: ClaimPipelineInput) -> ClaimPipelineResult:
        ...


class MockRocketRideClient(RocketRideClient, AIProvider):  # type: ignore
    """
    Hackathon-safe stand-in used whenever no real AI/RocketRide credentials are configured
    (see backend/.env.example -> ROCKETRIDE_MODE=mock). Produces realistic, internally
    consistent stage output using deterministic warranty-rule logic plus a small amount of
    randomness seeded from the claim's own serial number, so results are stable across
    repeated views of the same claim but still vary claim-to-claim.

    This is intentionally NOT a call to any real RocketRide endpoint — no vendor API syntax
    is invented here.

    Part 2.4: Implements AIProvider (provider-agnostic) while preserving RocketRideClient for backwards compat.
    """

    def _seeded_random(self, seed_text: str) -> random.Random:
        h = hashlib.sha256(seed_text.encode()).hexdigest()
        return random.Random(int(h[:8], 16))

    def run_pipeline(self, data: ClaimPipelineInput, context=None, execution_context=None) -> ClaimPipelineResult:  # type: ignore
        # Part 2.4: Accept AIProvider signature (pipeline_input, context, execution_context)
        # For backwards compat, `data` is ClaimPipelineInput; context/execution_context are optional and ignored for Mock (deterministic)
        # but they are logged for observability and future real provider will use them.
        # Keep deterministic behavior: same claim → same output.
        rng = self._seeded_random(data.serial_number or data.claim_code)
        result = ClaimPipelineResult()

        # Stage 1: DOCUMENT_EXTRACTION
        doc_conf = 0.95 if data.has_invoice else 0.35
        result.stage_outputs["DOCUMENT_EXTRACTION"] = {
            "invoice_present": data.has_invoice,
            "extraction_confidence": doc_conf,
        }
        if not data.has_invoice:
            result.missing_information.append("Invoice not provided")

        # Stage 2: POLICY_CHECK (deterministic-leaning; real rule enforcement happens in
        # backend/app/services/warranty_rules.py — this stage only *summarizes* it for AI use)
        fault_lower = data.fault_description.lower()
        likely_not_covered = any(term in fault_lower for term in
                                  [nc.lower() for nc in data.not_covered])
        result.stage_outputs["POLICY_CHECK"] = {
            "warranty_months": data.warranty_months,
            "likely_excluded_cause": likely_not_covered,
        }

        # Stage 3: EVIDENCE_ANALYSIS
        evidence_conf = 0.9 if data.has_photo else 0.5
        result.stage_outputs["EVIDENCE_ANALYSIS"] = {
            "photo_present": data.has_photo,
            "video_present": data.has_video,
            "fault_keywords": [w for w in
                               ["overheat", "noise", "hinge", "motor", "display", "e21", "leak"]
                               if w in fault_lower],
        }
        if not data.has_photo:
            result.missing_information.append("Product photo not provided")

        # Stage 4: SIMILAR_CASE_SEARCH
        similar_cases = rng.randint(3, 40)
        result.similar_case_count = similar_cases
        result.stage_outputs["SIMILAR_CASE_SEARCH"] = {"similar_case_count": similar_cases}

        # Stage 5: DECISION_AGENT
        base_confidence = (doc_conf + evidence_conf) / 2
        if likely_not_covered:
            recommendation = "DENY"
            base_confidence *= 0.8
            result.evidence.append("Fault description matches a policy exclusion")
        elif base_confidence > 0.75:
            recommendation = "REPAIR" if rng.random() > 0.35 else "REPLACE"
            result.evidence.append("Warranty is active")
            result.evidence.append("Fault appears consistent with a covered issue")
            result.evidence.append(f"{similar_cases} similar historical cases were found")
        else:
            recommendation = "MORE_INFORMATION_REQUIRED"

        result.recommendation = recommendation
        result.confidence = round(min(base_confidence, 0.97), 2)
        result.stage_outputs["DECISION_AGENT"] = {
            "recommendation": recommendation,
            "confidence": result.confidence,
        }

        # Stage 6: VALIDATOR (flags risk conditions; final human-review gate still lives in
        # backend/app/services/claim_workflow.py, this only *reports* signals)
        if data.customer_claim_count_90d >= 3:
            result.risk_flags.append(f"{data.customer_claim_count_90d} claims in 90 days")
        if recommendation == "DENY":
            result.risk_flags.append("Denial always requires human review")
        if result.confidence < 0.6:
            result.risk_flags.append("Low confidence recommendation")

        result.stage_outputs["VALIDATOR"] = {
            "risk_flags": result.risk_flags,
            "missing_information": result.missing_information,
        }

        return result


# ROCKETRIDE: connect real client here
# class RealRocketRideClient(RocketRideClient):
#     def __init__(self, api_key: str):
#         ...
#     def run_pipeline(self, data: ClaimPipelineInput) -> ClaimPipelineResult:
#         ...  # call the official RocketRide SDK/API per its documentation
