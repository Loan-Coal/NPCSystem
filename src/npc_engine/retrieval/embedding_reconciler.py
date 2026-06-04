"""
embedding_reconciler.py - Background stale-embedding reconciliation worker.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: mutate core graph properties other than embedding index timestamps.

Dependencies injected: GraphDB and EmbeddingIndex.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol


LOGGER = logging.getLogger(__name__)


CYPHER_SELECT_STALE_NODES = """
MATCH (n:Character)
WHERE n.is_active = true
  AND n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Character' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.archetype, '') + ' ' + coalesce(n.biography, '') + ' ' + coalesce(n.current_mood, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Event)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Event' AS kind,
       trim(coalesce(n.summary, '') + ' ' + coalesce(n.event_type, '') + ' ' + coalesce(n.location_id, '')) AS text,
       properties(n) AS payload
UNION ALL
MATCH (n:Location)
WHERE n.id IS NOT NULL
  AND n.last_graph_updated_at IS NOT NULL
  AND (
      n.last_embedding_indexed_at IS NULL
      OR n.last_graph_updated_at > n.last_embedding_indexed_at
  )
RETURN n.id AS id,
       'Location' AS kind,
       trim(coalesce(n.name, '') + ' ' + coalesce(n.descriptor, '') + ' ' + coalesce(n.region, '') + ' ' + coalesce(n.location_tag, '')) AS text,
       properties(n) AS payload
"""

# Batch write: store embedding vectors and mark-indexed timestamps in one query.
# This replaces N individual per-node mark-indexed calls.
CYPHER_BATCH_SET_EMBEDDINGS = """
UNWIND $nodes AS n
MATCH (m {id: n.id})
SET m.embedding = n.embedding,
    m.last_embedding_indexed_at = datetime(n.indexed_at)
"""


class _SessionProtocol(Protocol):
    async def run(self, query: str, **params) -> Any:
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
    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
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
        # Phase 1: collect stale node records, fully consuming the result before
        # running any write queries (session allows only one active result at a time).
        result = await session.run(CYPHER_SELECT_STALE_NODES)
        batch: list[dict] = []
        try:
            async for record in result:
                if len(batch) >= self._batch_size:
                    break
                batch.append({
                    "node_id": str(_record_value(record=record, key="id", default="")),
                    "kind": str(_record_value(record=record, key="kind", default="")),
                    "text": str(_record_value(record=record, key="text", default="")).strip(),
                    "payload": _record_value(record=record, key="payload", default={}),
                })
        finally:
            await result.consume()

        if not batch:
            return {"processed": 0, "failed": 0}

        # Phase 2: encode all texts in one batch call instead of N individual encodes.
        indexed_at = datetime.now(timezone.utc).isoformat()
        texts = [item["text"] or item["node_id"] for item in batch]
        vectors = await self._embedding_index.embed_batch(texts)

        # Phase 3: write all embedding vectors and mark-indexed timestamps in one query.
        write_nodes = [
            {"id": item["node_id"], "embedding": vector, "indexed_at": indexed_at}
            for item, vector in zip(batch, vectors)
        ]
        write_result = await session.run(CYPHER_BATCH_SET_EMBEDDINGS, nodes=write_nodes)
        await write_result.consume()

        return {"processed": len(batch), "failed": 0}


def _record_value(record: Any, key: str, default: Any) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    try:
        return record[key]
    except Exception:
        return default
