"""
RocketRide Provider — Part 2.5
Real provider adapter (interface only). Falls back to Mock if SDK unavailable.
DO NOT INVENT API — this is a safe unavailable-provider response.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.services.ai_provider import AIProvider
from rocketrider.pipeline import ClaimPipelineInput, ClaimPipelineResult

class RocketRideProvider(AIProvider):
    """
    Real RocketRide adapter. Requires SDK and API key.
    In Part 2.5, this is a safe stub that always falls back.
    When SDK is available, implement:
        - from rocketride import RocketRideClient as VendorClient
        - client = VendorClient(api_key=... )
        - response = client.run_workflow(...)
        - validate structured JSON output via Pydantic
        - map to ClaimPipelineResult
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.provider_name = "rocketride"
        self.model_name = "rocketride-v1"
        # Check SDK availability
        try:
            import rocketride  # type: ignore  # noqa
            self._available = True
        except ImportError:
            self._available = False

    def run_pipeline(self, pipeline_input: ClaimPipelineInput, context, execution_context) -> ClaimPipelineResult:
        if not self._available:
            raise RuntimeError(
                "RocketRide SDK not available. Set AI_PROVIDER=mock or install rocketride SDK. "
                "See rocketrider/README.md and docs/AI_PROVIDER_ARCHITECTURE.md"
            )
        if not self.api_key:
            raise RuntimeError("ROCKETRIDE_API_KEY missing. Set it in .env.")

        # If SDK were available, we would call it here, validate structured output, and map to ClaimPipelineResult
        # For now, raise to trigger fallback
        raise RuntimeError("RocketRide provider not fully implemented in Part 2.5 offline mode — fallback to mock")
