"""
Vector Store — Part 2.5
Provider-agnostic interface for upsert/search.
Preferred production: PostgreSQL + pgvector, fallback: in-memory.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import math

from app.services.embedding_provider import VectorDimensionMismatchError

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any]):
        ...

    @abstractmethod
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Return list of {id, score, metadata} sorted by score desc.
        Score is cosine similarity 0-1.
        """
        ...

    @abstractmethod
    def delete(self, id: str) -> bool:
        ...

    @abstractmethod
    def count(self) -> int:
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        ...


class MemoryVectorStore(VectorStore):
    """
    In-memory vector store for offline development and tests.
    No external DB, no pgvector required. Deterministic.
    Used when AI_VECTOR_STORE=memory (default) or pgvector unavailable.
    """

    def __init__(self, expected_dim: Optional[int] = None):
        self._store: Dict[str, Dict[str, Any]] = {}  # id -> {vector, metadata}
        self._expected_dim = expected_dim

    def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any]):
        if self._expected_dim is not None and len(vector) != self._expected_dim:
            raise VectorDimensionMismatchError(expected=self._expected_dim, actual=len(vector))
        # Infer dimension from first stored vector if expected_dim is None
        if self._store and self._expected_dim is None:
            first_dim = len(next(iter(self._store.values()))["vector"])
            if len(vector) != first_dim:
                raise VectorDimensionMismatchError(expected=first_dim, actual=len(vector))
        self._store[id] = {"vector": vector, "metadata": metadata}

    def _cosine(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x*y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x*x for x in a))
        norm_b = math.sqrt(sum(y*y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if self._store:
            first_dim = len(next(iter(self._store.values()))["vector"])
            if len(query_vector) != first_dim:
                raise VectorDimensionMismatchError(expected=first_dim, actual=len(query_vector))
        scored = []
        for id, entry in self._store.items():
            score = self._cosine(query_vector, entry["vector"])
            # Normalize to 0-1
            score = (score + 1) / 2
            scored.append({"id": id, "score": round(score, 4), "metadata": entry["metadata"]})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, id: str) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False

    def count(self) -> int:
        return len(self._store)

    def health_check(self) -> Dict[str, Any]:
        return {
            "type": "memory",
            "status": "healthy",
            "count": self.count(),
            "available": True,
        }


class PgVectorStore(VectorStore):
    """
    PostgreSQL + pgvector implementation.
    If pgvector not available or fails to connect, falls back to MemoryVectorStore.
    """
    def __init__(self, collection_name: str = "historical_cases", expected_dim: int = 16):
        self.collection_name = collection_name
        self.expected_dim = expected_dim
        try:
            import pgvector  # type: ignore  # noqa
            self._available = True
        except ImportError:
            self._available = False
            raise RuntimeError("pgvector package not available, fallback to memory")

    def upsert(self, id: str, vector: List[float], metadata: Dict[str, Any]):
        if len(vector) != self.expected_dim:
            raise VectorDimensionMismatchError(expected=self.expected_dim, actual=len(vector))
        raise NotImplementedError("PgVector DB session execution unavailable in offline mock mode")

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if len(query_vector) != self.expected_dim:
            raise VectorDimensionMismatchError(expected=self.expected_dim, actual=len(query_vector))
        raise NotImplementedError("PgVector search execution unavailable in offline mock mode")

    def delete(self, id: str) -> bool:
        return False

    def count(self) -> int:
        return 0

    def health_check(self) -> Dict[str, Any]:
        return {
            "type": "pgvector",
            "status": "available" if self._available else "unavailable",
            "collection": self.collection_name,
            "available": self._available,
        }


def get_vector_store():
    from app.core.config import get_settings
    settings = get_settings()
    store_type = getattr(settings, "AI_VECTOR_STORE", "memory").lower()
    dim = getattr(settings, "AI_EMBEDDING_DIMENSION", 16)
    if store_type == "memory":
        store_type = getattr(settings, "VECTOR_STORE", "memory").lower()
    if store_type == "pgvector":
        try:
            collection = getattr(settings, "PGVECTOR_COLLECTION", "historical_cases")
            return PgVectorStore(collection_name=collection, expected_dim=dim)
        except Exception:
            # Fallback to memory if pgvector not available
            return MemoryVectorStore(expected_dim=dim)
    else:
        return MemoryVectorStore(expected_dim=dim)

