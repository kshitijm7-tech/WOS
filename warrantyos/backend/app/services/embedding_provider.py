"""
Embedding Provider — Part 2.5
Provider-agnostic interface for text embeddings.
Offline mock by default, pgvector/real provider optional.
"""

from abc import ABC, abstractmethod
from typing import List
import hashlib
import math

class VectorDimensionMismatchError(ValueError):
    """Raised when embedding dimension does not match vector store expectation."""
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual
        self.error_code = "VECTOR_DIMENSION_MISMATCH"
        super().__init__(f"VECTOR_DIMENSION_MISMATCH: expected dimension {expected}, got {actual}")


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Return embedding vector for text. Must be deterministic for same text."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""
        ...

    def validate_vector_dimension(self, vector: List[float]) -> None:
        """Validate that vector dimension matches expected dimension."""
        if len(vector) != self.dimension():
            raise VectorDimensionMismatchError(expected=self.dimension(), actual=len(vector))


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic mock embedding — no external calls, no API keys.
    Uses hashlib to generate a reproducible float vector from text.
    For Part 2.6, this is the default active provider (AI_EMBEDDING_PROVIDER=mock).
    """

    def __init__(self, dim: int = 16):
        self._dim = dim

    def dimension(self) -> int:
        return self._dim

    def embed(self, text: str) -> List[float]:
        # Deterministic: hash text and expand to dim floats in [-1, 1]
        h = hashlib.md5(text.encode()).hexdigest()
        # Use hash to seed floats
        vec = []
        for i in range(self._dim):
            # Take 2 hex chars per dim, convert to 0-255, normalize to -1..1
            hex_pair = h[(i*2) % len(h): (i*2) % len(h) + 2]
            if len(hex_pair) < 2:
                hex_pair = "00"
            val = int(hex_pair, 16) / 127.5 - 1.0
            # Add slight variation based on i to avoid repetition
            vec.append(round(val * (0.5 + 0.5 * math.sin(i)), 4))
        self.validate_vector_dimension(vec)
        return vec


def get_embedding_provider():
    from app.core.config import get_settings
    settings = get_settings()
    provider = getattr(settings, "AI_EMBEDDING_PROVIDER", "mock").lower()
    dim = getattr(settings, "AI_EMBEDDING_DIMENSION", 16)
    if provider == "mock":
        return MockEmbeddingProvider(dim=dim)
    else:
        # Fallback to mock if real not available
        return MockEmbeddingProvider(dim=dim)

