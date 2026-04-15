"""
vector_store_factory.py - Backend selector for vector store implementations.

Does NOT: compute embeddings.

Dependencies injected: Settings.
"""

from config import Settings
from retrieval.vector_store_protocol import VectorSearchResult, VectorStoreProtocol


def _dot_similarity(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def _validate_top_k(top_k: int) -> None:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")


class InMemoryVectorStore(VectorStoreProtocol):
    """Simple in-memory vector store for local and test usage."""

    def __init__(self):
        self._entries: dict[str, dict] = {}

    async def upsert(self, item_id: str, vector: list[float], payload: dict) -> None:
        self._entries[item_id] = {
            "vector": [*vector],
            "payload": dict(payload),
        }

    async def search(self, query_vector: list[float], top_k: int) -> list[VectorSearchResult]:
        _validate_top_k(top_k)
        scored: list[VectorSearchResult] = [
            {
                "id": item_id,
                "score": _dot_similarity(query_vector, entry["vector"]),
                "payload": dict(entry["payload"]),
            }
            for item_id, entry in self._entries.items()
        ]
        ranked = sorted(scored, key=lambda row: float(row["score"]), reverse=True)
        return ranked[:top_k]

    async def delete(self, item_id: str) -> None:
        self._entries.pop(item_id, None)


def create_vector_store(settings: Settings) -> VectorStoreProtocol:
    """Create vector store backend from configuration."""

    if settings.VECTOR_STORE_BACKEND == "memory":
        return InMemoryVectorStore()
    if settings.VECTOR_STORE_BACKEND == "qdrant":
        raise NotImplementedError("Qdrant backend is not implemented yet")
    raise ValueError(f"Unsupported VECTOR_STORE_BACKEND: {settings.VECTOR_STORE_BACKEND}")
