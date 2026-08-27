"""
embedding_reconciler.py - Background stale-embedding reconciliation worker.
Layer: retrieval
Purpose: Periodic worker that heals stale embeddings using graph timestamps.

Does NOT: own the vector store's contents — it drives retrieval.embedding.corpus, which
          does (DEC-208) — or mutate core graph properties other than embedding fields.

Dependencies injected: GraphDB and EmbeddingIndex.
Used by: api/dependencies.py (scheduler wiring).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Protocol

from npc_engine.graph.infra.embedding_sync_queries import batch_set_embeddings, select_stale_nodes
from npc_engine.retrieval.embedding.corpus import CorpusStoreProtocol, ensure_corpus
from npc_engine.schema.corpus_models import CorpusReport


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


class _EmbeddingIndexProtocol(CorpusStoreProtocol, Protocol):
    """What the reconciler needs of an index: encode a batch, and be a corpus store.

    It extends CorpusStoreProtocol rather than duplicating it because ensure_corpus_once
    hands this same object on as the store to populate. The text-embedding `upsert` is
    NOT here: the reconciler has never called it, and declaring a method no implementor
    is exercised on is how a mock drifts from the adapter it stands in for.
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
            return await self.reconcile_in_session(session)

    async def ensure_corpus_once(self) -> CorpusReport:
        """Reconcile until dry and load every embedded node into the vector store.

        Returns:
            The CorpusReport for this sweep.
        """

        async with self._graph_db.get_session() as session:
            return await ensure_corpus(
                session, self._embedding_index, self, batch_size=self._batch_size,
            )

    async def run_forever(self) -> None:
        """Populate the corpus in a loop until task cancellation.

        Calls ensure_corpus, not reconcile_once: writing `n.embedding` and never
        propagating it to the vector store is what left the store all-delete-no-insert
        (DEC-208). One owner, one entry point — this loop, boot, and the rehydrate route
        all go through the same function.

        Logs cycle stats when at least one node was processed or read.
        Swallows non-cancellation exceptions and retries after the configured interval.

        Raises:
            asyncio.CancelledError: Propagated on task cancellation.
        """

        while True:
            try:
                report = await self.ensure_corpus_once()
                if report.reconcile_passes > 1 or report.nodes_read > 0:
                    LOGGER.info(
                        "embedding reconcile cycle finished: passes=%s nodes_read=%s "
                        "upserted=%s missing_embedding=%s item_count=%s",
                        report.reconcile_passes,
                        report.nodes_read,
                        report.upserted,
                        report.missing_embedding,
                        report.fingerprint.item_count,
                    )
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                LOGGER.info("embedding reconciler cancelled")
                raise
            except Exception:
                LOGGER.exception("embedding reconciler cycle failed")
                await asyncio.sleep(self._interval_seconds)

    async def reconcile_in_session(self, session: _SessionProtocol) -> dict[str, int]:
        """Run one reconciliation cycle on a session the caller already holds.

        Public because ensure_corpus drives it in a loop until it goes dry, on the same
        session it then reads the corpus back from (DEC-208). It was private, which is
        why corpus population and reconciliation could only be sequenced by task-start
        order in a lifespan.

        Args:
            session: Active Neo4j async session.

        Returns:
            Dict with keys ``processed`` (successful writes) and ``failed``.
        """

        model_name = self._embedding_index.model_name
        batch = await select_stale_nodes(
            session, self._batch_size, embedding_model=model_name,  # type: ignore[arg-type]
        )

        if not batch:
            return {"processed": 0, "failed": 0}

        indexed_at = datetime.now(timezone.utc).isoformat()
        texts = [item["text"] or item["node_id"] for item in batch]
        vectors = await self._embedding_index.embed_batch(texts)

        write_nodes = [
            {
                "id": item["node_id"],
                "embedding": vector,
                "indexed_at": indexed_at,
                "embedding_model": model_name,
                "embedding_dim": len(vector),
            }
            for item, vector in zip(batch, vectors)
        ]
        await batch_set_embeddings(session, write_nodes)  # type: ignore[arg-type]
        return {"processed": len(batch), "failed": 0}

