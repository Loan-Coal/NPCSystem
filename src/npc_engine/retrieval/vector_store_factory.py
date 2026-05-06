"""
vector_store_factory.py - Backend selector for vector store implementations.

Does NOT: compute embeddings.

Dependencies injected: Settings.
"""

from npc_engine.config import Settings
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult, VectorStoreProtocol


def _dot_similarity(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


def _validate_top_k(top_k: int) -> None:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")


class InMemoryVectorStore(VectorStoreProtocol):
    """Simple in-memory vector store for local and test usage."""

    def __init__(self) -> None:
        """Initialise an empty in-memory vector store."""

        self._entries: dict[str, dict] = {}

    async def upsert(self, item_id: str, vector: list[float], payload: dict) -> None:
        """Insert or replace one vector entry.

        Args:
            item_id: Unique identifier for the item.
            vector: Embedding vector; stored as a new list copy.
            payload: Metadata dict; stored as a shallow copy.
        """

        self._entries[item_id] = {
            "vector": [*vector],
            "payload": dict(payload),
        }

    async def search(self, query_vector: list[float], top_k: int) -> list[VectorSearchResult]:
        """Return top-k results ranked by dot-product similarity.

        Args:
            query_vector: Embedding to compare against stored vectors.
            top_k: Maximum results to return; must be greater than 0.

        Returns:
            List of up to top_k VectorSearchResult dicts sorted by descending score.

        Raises:
            ValueError: If top_k is not greater than 0.
        """

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
        """Remove an entry by id; no-op if not present.

        Args:
            item_id: Identifier of the entry to remove.
        """

        self._entries.pop(item_id, None)


def create_vector_store(settings: Settings) -> VectorStoreProtocol:
    """Create a vector store backend from configuration.

    Args:
        settings: Application settings; ``VECTOR_STORE_BACKEND`` selects the backend.

    Returns:
        A concrete VectorStoreProtocol implementation.

    Raises:
        NotImplementedError: If the backend is recognised but not yet implemented (``qdrant``).
        ValueError: If the backend name is unknown.
    """

    if settings.VECTOR_STORE_BACKEND == "memory":
        return InMemoryVectorStore()
    if settings.VECTOR_STORE_BACKEND == "qdrant":
        raise NotImplementedError("Qdrant backend is not implemented yet")
    raise ValueError(f"Unsupported VECTOR_STORE_BACKEND: {settings.VECTOR_STORE_BACKEND}")
