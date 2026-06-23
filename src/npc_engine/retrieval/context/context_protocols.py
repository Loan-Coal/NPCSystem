"""
Module: context_protocols
Layer: retrieval
Purpose: Shared Protocol types for the retrieval layer — currently EmbeddingIndexProtocol.
Does NOT: implement any retrieval logic; Protocol definitions only.
Dependencies: retrieval.vector_store_protocol.
Dependencies injected: none.
Used by: retrieval.context_builder, engines.dialogue.dialogue_handler
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.retrieval.embedding.vector_store_protocol import VectorSearchResult


class EmbeddingIndexProtocol(Protocol):
    """Minimal protocol required by context builder and dialogue handler."""

    async def search(
        self,
        query: str,
        top_k: int,
        filter_ids: set[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Return top-k semantic retrieval rows.

        Args:
            query: Text query to embed and search.
            top_k: Maximum number of results to return.
            filter_ids: When provided, restrict results to items with these IDs.

        Returns:
            List of VectorSearchResult dicts sorted by descending score.
        """
