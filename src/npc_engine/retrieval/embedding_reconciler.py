"""
embedding_reconciler.py - Background stale-embedding reconciliation worker.
Layer: retrieval
Purpose: Periodic worker that heals stale embeddings using graph timestamps.

Does NOT: mutate core graph properties other than embedding index timestamps.

Dependencies injected: GraphDB and EmbeddingIndex.
Used by: api/dependencies.py (scheduler wiring).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol

from npc_engine.graph.embedding_sync_queries import batch_set_embeddings, select_stale_nodes


LOGGER = logging.getLogger(__name__)


class _SessionProtocol(Protocol):
    async def run(self, query: str, **params: Any) -> Any:
        """Execute an async Cypher query.

        Args:
            query: Cypher query string.
            **params: Named parameters bound into the query.

        Returns:
            An async-iterable result cursor.
        """


class _GraphDbProtocol(Protocol):
    def get_session(self) -> Any:
        """Return an async context manager that yields a _SessionProtocol instance."""


class _EmbeddingIndexProtocol(Protocol):
    async def upsert(self, item_id: str, text: str, payload: dict[str, Any]) -> None:
        """Upsert one embedding row.

        Args:
            item_id: Unique identifier for the item.
            text: Raw text to embed.
            payload: Metadata stored alongside the embedding.
        """

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts and return their embedding vectors.

        Called once per reconciliation cycle instead of encoding inside
        each individual upsert call. Reduces encoder invocations from N to 1.

        Args:
            texts: Raw text strings to encode; empty list returns empty list.

        Returns:
            List of float vectors, one per input text, in the same order.
        """


class EmbeddingReconciler:
    """Periodic reconciler that heals stale embeddings from npc_engine.graph timestamps."""

    def __init__(
        self,
        graph_db: _GraphDbProtocol,
        embedding_index: _EmbeddingIndexProtocol,
        interval_seconds: int,
        batch_size: int = 200,
    ) -> None:
        """Initialise the reconciler.

        Args:
            graph_db: Graph database handle used to query stale nodes.
            embedding_index: Embedding index used to batch-encode node texts.
            interval_seconds: Seconds between reconciliation cycles; must be greater than 0.
            batch_size: Maximum nodes to process per cycle; must be greater than 0.

        Raises:
            ValueError: If interval_seconds or batch_size is not greater than 0.
        """

        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0")
        self._graph_db = graph_db
        self._embedding_index = embedding_index
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size

    async def reconcile_once(self) -> dict[str, int]:
        """Run one reconciliation cycle over all stale nodes.

        Returns:
            Dict with keys ``processed`` (successful writes) and ``failed`` (error count).
        """

        async with self._graph_db.get_session() as session:
            return await self._reconcile_in_session(session=session)

    async def run_forever(self) -> None:
        """Run reconciliation cycles in a loop until task cancellation.

        Logs cycle stats when at least one node was processed or failed.
        Swallows non-cancellation exceptions and retries after the configured interval.

        Raises:
            asyncio.CancelledError: Propagated on task cancellation.
        """

        while True:
            try:
                stats = await self.reconcile_once()
                if stats["processed"] > 0 or stats["failed"] > 0:
                    LOGGER.info(
                        "embedding reconcile cycle finished: processed=%s failed=%s",
                        stats["processed"],
                        stats["failed"],
                    )
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                LOGGER.info("embedding reconciler cancelled")
                raise
            except Exception:
                LOGGER.exception("embedding reconciler cycle failed")
                await asyncio.sleep(self._interval_seconds)

    async def _reconcile_in_session(self, session: _SessionProtocol) -> dict[str, int]:
        batch = await select_stale_nodes(session, self._batch_size)  # type: ignore[arg-type]

        if not batch:
            return {"processed": 0, "failed": 0}

        indexed_at = datetime.now(timezone.utc).isoformat()
        texts = [item["text"] or item["node_id"] for item in batch]
        vectors = await self._embedding_index.embed_batch(texts)

        write_nodes = [
            {"id": item["node_id"], "embedding": vector, "indexed_at": indexed_at}
            for item, vector in zip(batch, vectors)
        ]
        await batch_set_embeddings(session, write_nodes)  # type: ignore[arg-type]
        return {"processed": len(batch), "failed": 0}

