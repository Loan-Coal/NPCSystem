"""
vector_store_protocol.py - Protocol for vector search backends.

Does NOT: define backend factory logic.

Dependencies injected: None.
"""

from typing import Protocol, TypedDict


class VectorSearchResult(TypedDict):
    """Typed vector search row contract across backends."""

    id: str
    score: float
    payload: dict


class VectorStoreProtocol(Protocol):
    """Contract for vector storage implementations."""

    async def upsert(self, item_id: str, vector: list[float], payload: dict) -> None:
        """Insert or update one vector item."""

    async def search(self, query_vector: list[float], top_k: int) -> list[VectorSearchResult]:
        """Return top-k payload results sorted by score desc."""

    async def delete(self, item_id: str) -> None:
        """Delete one vector item if present."""
