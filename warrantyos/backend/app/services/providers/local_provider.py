"""
Local LLM Provider — Part 2.5
Stub for future local model (e.g., Ollama). Offline, no external calls in Part 2.5.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from app.services.ai_provider import AIProvider
from rocketrider.pipeline import ClaimPipelineInput, ClaimPipelineResult

class LocalLLMProvider(AIProvider):
    """
    Local LLM adapter (e.g., Ollama). Not implemented in Part 2.5, falls back to mock.
    When implemented, it would:
      - Load model from AI_MODEL env (e.g., ollama/llama3)
      - Build structured prompt from AIAnalysisContext (sanitized)
      - Call local LLM with response_format=json_object
      - Validate via Pydantic (ClaimPipelineResult)
      - Never store chain-of-thought
    """

    def __init__(self, model: str = "mock-v1"):
        self.model = model
        self.provider_name = "local"
        self.model_name = model

    def run_pipeline(self, pipeline_input: ClaimPipelineInput, context, execution_context) -> ClaimPipelineResult:
        raise RuntimeError(
            "Local LLM provider not implemented in Part 2.5 offline mode. "
            "Use AI_PROVIDER=mock. See docs/AI_PROVIDER_ARCHITECTURE.md"
        )
