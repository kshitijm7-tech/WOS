"""
AI Provider Interface — Part 2.4
Provider-agnostic abstraction. Orchestrator depends only on this, never on Mock directly.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rocketrider.pipeline import ClaimPipelineInput, ClaimPipelineResult
    from app.schemas.evidence_ai import AIAnalysisContext
    from app.schemas.ai_execution import AIExecutionContext


class AIProvider(ABC):
    """
    Abstract provider. Implementations: MockRocketRideClient (offline), future RocketRide/LocalLLM.
    Must be deterministic and offline for Part 2.4.
    """

    @abstractmethod
    def run_pipeline(
        self,
        pipeline_input: "ClaimPipelineInput",
        context: "AIAnalysisContext",
        execution_context: "AIExecutionContext",
    ) -> "ClaimPipelineResult":
        """
        Execute the 6-stage pipeline. Must return ClaimPipelineResult.
        Must not make external calls in Part 2.4 (offline).
        Must be deterministic for same input+context.
        """
        ...
