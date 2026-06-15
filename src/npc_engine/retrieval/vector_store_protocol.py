"""
vector_store_protocol.py - Protocol for vector search backends.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: define backend factory logic.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Protocol, TypedDict


class VectorSearchResult(TypedDict):
    """Typed vector search row contract across backends."""

    id: str
    score: float
    payload: dict


class VectorStoreProtocol(Protocol):
    """Contract for vector storage implementations."""

    async def upsert(self, item_id: str, vector: list[float], payload: dict) -> None:
        """Insert or update one vector item.

        Args:
            item_id: Unique identifier for the item.
            vector: Embedding vector for the item.
            payload: Arbitrary metadata stored alongside the vector.
        """

    async def search(self, query_vector: list[float], top_k: int) -> list[VectorSearchResult]:
        """Return top-k payload results sorted by score desc.

        Args:
            query_vector: Query embedding to compare against stored vectors.
            top_k: Maximum number of results to return; must be greater than 0.

        Returns:
            List of up to top_k results sorted by descending similarity score.
        """

    async def delete(self, item_id: str) -> None:
        """Delete one vector item if present.

        Args:
            item_id: Identifier of the item to remove; no-op if not found.
        """
