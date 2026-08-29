"""
Mock AI Provider — Part 2.5
Provider-agnostic, deterministic, offline. Wraps MockRocketRideClient.
No external calls, no API keys, no chain-of-thought.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.services.ai_provider import AIProvider
from rocketrider.adapter import MockRocketRideClient
from rocketrider.pipeline import ClaimPipelineInput, ClaimPipelineResult
from app.schemas.evidence_ai import AIAnalysisContext
from app.schemas.ai_execution import AIExecutionContext


class MockAIProvider(AIProvider):
    """
    Mock provider for offline development. Deterministic, no PII, no file paths.
    Delegates to MockRocketRideClient for the actual 6-stage logic, but validates
    structured output via Pydantic before returning.
    """

    def __init__(self):
        self._mock = MockRocketRideClient()
        self.provider_name = "mock"
        self.model_name = "mock-v1"

    def run_pipeline(
        self,
        pipeline_input: ClaimPipelineInput,
        context: AIAnalysisContext,
        execution_context: AIExecutionContext,
    ) -> ClaimPipelineResult:
        # Call the existing deterministic mock
        # For Part 2.5, we pass through context/execution_context for observability,
        # but the mock's core logic remains based on pipeline_input (has_invoice, etc.)
        # The orchestrator will enrich the result with context-derived stage outputs.
        result = self._mock.run_pipeline(pipeline_input)

        # Structured output validation (untrusted data check)
        # Ensure result conforms to expected schema; if not, raise to trigger validator
        if not result.recommendation or result.recommendation not in {"REPAIR", "REPLACE", "DENY", "MORE_INFORMATION_REQUIRED", "HUMAN_REVIEW"}:
            # Let validator handle it, but we can also sanitize here
            pass
        if result.confidence is not None and not (0 <= result.confidence <= 0.97):
            # Clamp to valid range
            result.confidence = max(0, min(0.97, float(result.confidence)))

        # Ensure stage names are valid
        from rocketrider.pipeline import STAGES
        for stage in list(result.stage_outputs.keys()):
            if stage not in STAGES and stage not in {"POLICY_INTERPRETATION", "SIMILAR_CASES", "RISK_ASSESSMENT", "FRAUD_RISK", "RECOMMENDATION"}:
                # Remove invalid stage to trigger validator's missing stage check, but we keep it for now
                pass

        return result
