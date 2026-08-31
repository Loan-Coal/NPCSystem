"""
vector_store_protocol.py - Protocol for vector search backends.
Layer: retrieval
Purpose: Protocol for vector search backends.

Does NOT: define backend factory logic.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Protocol, TypedDict, Any


class VectorSearchResult(TypedDict):
    """Typed vector search row contract across backends."""

    id: str
    score: float
    payload: dict[str, Any]


class VectorStoreProtocol(Protocol):
    """Contract for vector storage implementations."""

    async def upsert(self, item_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        """Insert or update one vector item.

        Args:
            item_id: Unique identifier for the item.
            vector: Embedding vector for the item.
            payload: Arbitrary metadata stored alongside the vector.
        """

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        filter_ids: set[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Return top-k payload results sorted by score desc, ranked WITHIN the filter.

        ``filter_ids`` is part of this protocol rather than applied by the caller because
        filtering must precede ranking (DEC-209). A caller that ranks the whole store and
        then discards the out-of-scope rows spends its top_k on the majority it is about
        to throw away, so a filtered search over a mixed store returns 0-1 rows instead of
        top_k. Every implementation must restrict the candidate set BEFORE scoring.

        Args:
            query_vector: Query embedding to compare against stored vectors.
            top_k: Maximum number of results to return; must be greater than 0.
            filter_ids: When given, only these ids are candidates. An EMPTY set means
                no candidates and yields no results — it never means "everything".

        Returns:
            List of up to top_k results sorted by descending similarity score.
        """

    async def delete(self, item_id: str) -> None:
        """Delete one vector item if present.

        Args:
            item_id: Identifier of the item to remove; no-op if not found.
        """

    async def count(self) -> int:
        """Return how many entries the store currently holds.

        Part of the protocol because DEC-208's report — and the corpus fingerprint a
        generation record carries — must be answerable through the interface rather than
        by reaching into one backend's internals. A backend that cannot count cannot say
        whether hydration worked, and a silent item_count of 0 costs a night of
        generation and then reads as a null result rather than as a failure.

        Returns:
            Number of stored entries.
        """
