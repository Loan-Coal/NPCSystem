"""
Module: corpus
Layer: retrieval
Purpose: THE owner of the vector store's contents — reconciles embeddings until dry, then
         loads every embedded node out of Neo4j and into the store, and reports what it did.
Does NOT: encode text itself (the reconciler owns the embedding TEXT), query the graph
          directly (graph.infra.embedding_load_queries owns the Cypher), or read Settings.
Dependencies injected: session, a store protocol, a reconciler protocol — all passed in.
Used by: retrieval.embedding.embedding_reconciler (run_forever), api.routes.admin
         .vector_store (the rehydrate route), npc_engine.main (boot hydration).

Why this file exists
--------------------
`EmbeddingIndex.upsert` had ZERO callers anywhere in `src/`. The reconciler wrote
`n.embedding` in Neo4j and stopped there; the three paths that reached the store — the
event handler, the gossip handler, the reindex job — all called `delete`. The vector
store was all-delete-no-insert from the day it was written, which is a single sufficient
cause for `tierB.items == 0` on every run ever recorded (DEC-208).

So this is not a cache warm-up. It is the system's only insert path, and it is a function
that RETURNS A VALUE rather than an ordering contract between two asyncio tasks that you
could only discover by reading a lifespan.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from neo4j import AsyncSession

from npc_engine.graph.infra.embedding_load_queries import (
    count_nodes_missing_embedding,
    select_embedded_nodes,
)
from npc_engine.schema.corpus_models import CorpusFingerprint, CorpusReport

__all__ = [
    "MAX_RECONCILE_PASSES",
    "ensure_corpus",
    "read_corpus_fingerprint",
    "refresh_corpus_node",
    "refresh_corpus_nodes_batch",
]

MAX_RECONCILE_PASSES: int = 100
"""Hard stop on the reconcile-until-dry loop.

Reconciliation is dry when a pass processes zero nodes. A node whose write does not clear
its own staleness would otherwise loop forever and hang boot; this turns that into a
bounded run with a non-zero ``missing_embedding`` in the report.
"""

_FINGERPRINT_FIELD_SEPARATOR = "\x1f"
_FINGERPRINT_ROW_SEPARATOR = "\n"


class CorpusStoreProtocol(Protocol):
    """The two store operations corpus population needs, and no more.

    Deliberately smaller than EmbeddingIndex: ``ensure_corpus`` must never encode, so it
    is not given anything that could. The stored vectors are reused verbatim — the
    sentence encoder normalises, so the store's dot product is already cosine and a
    re-encode would only be a chance for two encode paths to disagree.
    """

    async def upsert_vector(self, item_id: str, vector: list[float], payload: dict[str, Any]) -> None:
        """Store a precomputed vector under item_id.

        Args:
            item_id: Unique identifier for the item.
            vector: Embedding vector, already computed.
            payload: Metadata stored alongside the vector.
        """

    async def count(self) -> int:
        """Return how many entries the store currently holds."""

    @property
    def model_name(self) -> str:
        """Return the embedding model identifier this index encodes with."""


class CorpusReconcilerProtocol(Protocol):
    """The single reconciliation step corpus population drives."""

    async def reconcile_in_session(self, session: AsyncSession) -> dict[str, int]:
        """Run one reconciliation cycle on an existing session.

        Args:
            session: Active Neo4j async session.

        Returns:
            Dict with keys ``processed`` and ``failed``.
        """


async def _reconcile_until_dry(
    session: AsyncSession, reconciler: CorpusReconcilerProtocol
) -> int:
    """Run reconciliation cycles until one processes nothing; return the pass count.

    One `reconcile_once` caps at batch_size over a `select_stale_nodes` that has no
    ORDER BY, so a single sweep leaves a partial corpus in undefined row order once a
    world exceeds the batch. 51 embeddable nodes fit today; the demo world will not.
    """
    passes = 0
    while passes < MAX_RECONCILE_PASSES:
        stats = await reconciler.reconcile_in_session(session)
        passes += 1
        if stats["processed"] == 0:
            break
    return passes


def _fingerprint_rows(rows: list[dict[str, Any]], model_name: str) -> str:
    """Digest corpus MEMBERSHIP — sorted node ids and the model that embedded each."""
    lines = sorted(
        f"{row['node_id']}{_FINGERPRINT_FIELD_SEPARATOR}{row['embedding_model'] or model_name}"
        for row in rows
    )
    joined = _FINGERPRINT_ROW_SEPARATOR.join(lines)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _resolve_dim(rows: list[dict[str, Any]]) -> int:
    """Return the stored vector width, preferring the node's declared embedding_dim."""
    for row in rows:
        declared = row.get("embedding_dim")
        if declared is not None:
            return int(declared)
        if row["embedding"]:
            return len(row["embedding"])
    return 0


async def _load_all_embedded_nodes(session: AsyncSession, batch_size: int) -> list[dict[str, Any]]:
    """Page through every embedded node in deterministic id order."""
    rows: list[dict[str, Any]] = []
    while True:
        page = await select_embedded_nodes(session, skip=len(rows), limit=batch_size)
        rows.extend(page)
        if len(page) < batch_size:
            return rows



async def _upsert_rows(index: CorpusStoreProtocol, rows: list[dict[str, Any]]) -> int:
    """Write every loaded row into the store; return how many were written."""
    for row in rows:
        payload = {key: value for key, value in row["payload"].items() if value is not None}
        await index.upsert_vector(
            item_id=row["node_id"], vector=row["embedding"], payload=payload
        )
    return len(rows)


async def _build_fingerprint(
    index: CorpusStoreProtocol, rows: list[dict[str, Any]]
) -> CorpusFingerprint:
    """Assemble the corpus identity a generation record cites."""
    return CorpusFingerprint(
        item_count=await index.count(),
        embedding_model=index.model_name,
        embedding_dim=_resolve_dim(rows),
        corpus_sha=_fingerprint_rows(rows, index.model_name),
    )


async def read_corpus_fingerprint(
    *,
    session: AsyncSession,
    index: CorpusStoreProtocol,
    batch_size: int,
) -> CorpusFingerprint:
    """Report corpus identity WITHOUT writing the store — the read-only half of the pair.

    `ensure_corpus` computes the same fingerprint as a side effect of populating the
    store. That is the wrong shape for a freeze check: DEC-210 Decision 2 wants a P10
    gate that asserts the corpus did not move between a run's first turn and its last,
    and a check that rehydrates on the way past is not a check.

    Without this, `GET /v1/admin/debug/vector-store` returned `corpus_sha=""`
    unconditionally, so the ONE field carrying membership was empty in every generation
    record DEC-210 produced. `item_count` cannot substitute: swapping one node for
    another leaves it identical.

    Args:
        session: Active Neo4j async session.
        index: The vector store, read for its item count and model name only.
        batch_size: Page size for the embedded-node scan.
    Returns:
        A CorpusFingerprint with a populated corpus_sha. An EMPTY corpus still yields a
        digest — the caller distinguishes empty from unreachable by item_count, and a
        raise here would collapse that distinction.
    """
    rows = await _load_all_embedded_nodes(session, batch_size)
    return await _build_fingerprint(index, rows)


async def ensure_corpus(
    session: AsyncSession,
    index: CorpusStoreProtocol,
    reconciler: CorpusReconcilerProtocol,
    *,
    batch_size: int,
) -> CorpusReport:
    """Reconcile embeddings until dry, load them all into the vector store, and report.

    This is the ONLY path that writes the vector store. Boot hydration, the admin
    rehydrate route and the reconciler's own loop all call this same function, so there
    is one definition of "the corpus is populated" instead of three.

    Args:
        session: Active Neo4j async session.
        index: Vector store to populate.
        reconciler: Reconciler driven until it processes nothing.
        batch_size: Page size for both reconciliation and the load; must be > 0.

    Returns:
        A CorpusReport carrying the counts and the fingerprint the generation record
        needs. A report with ``nodes_read == 0`` is a FAILURE the caller must surface —
        a silent empty corpus reads afterwards as a null result rather than as a fault.

    Raises:
        ValueError: If batch_size is not greater than 0.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    passes = await _reconcile_until_dry(session, reconciler)
    rows = await _load_all_embedded_nodes(session, batch_size)
    upserted = await _upsert_rows(index, rows)
    return CorpusReport(
        nodes_read=len(rows),
        upserted=upserted,
        missing_embedding=await count_nodes_missing_embedding(session),
        reconcile_passes=passes,
        fingerprint=await _build_fingerprint(index, rows),
    )


async def refresh_corpus_node(
    session: AsyncSession,
    index: CorpusStoreProtocol,
    reconciler: CorpusReconcilerProtocol,
    *,
    node_id: str,
) -> bool:
    """Re-embed whatever is stale, then write THIS node's entry into the store.

    The incremental half of DEC-210. It runs one reconciliation pass rather than
    embedding the node itself: `select_stale_nodes` builds the embedding TEXT with a
    specific per-label concatenation, and a second implementation of that text — here,
    in a handler — is exactly the silent-divergence factory DEC-208 rejected as its
    option (b). One pass is bounded by batch_size; the periodic loop still catches
    anything a burst leaves behind.

    Args:
        session: Active Neo4j async session.
        index: Vector store to write into.
        reconciler: Reconciler run for a single pass.
        node_id: The node whose entry should be refreshed.

    Returns:
        True when an entry was written; False when the node still carries no embedding.
    """
    await reconciler.reconcile_in_session(session)
    rows = await select_embedded_nodes(session, skip=0, limit=1, node_ids=[node_id])
    if not rows:
        return False
    await _upsert_rows(index, rows)
    return True


async def refresh_corpus_nodes_batch(
    session: AsyncSession,
    index: CorpusStoreProtocol,
    reconciler: CorpusReconcilerProtocol,
    *,
    node_ids: list[str],
) -> int:
    """Reconcile once, then upsert all given nodes in a single pass.

    The batch companion of ``refresh_corpus_node``: one reconciliation pass
    covers all pending embeddings, then all ``node_ids`` are queried and
    upserted together.  Use this when multiple nodes need refreshing in one
    call — it drives O(1) reconcile passes instead of O(len(node_ids)).

    Args:
        session: Active Neo4j async session.
        index: Vector store to write into.
        reconciler: Reconciler run exactly once for the whole batch.
        node_ids: Nodes whose entries should be refreshed.

    Returns:
        Number of entries written to the store (may be less than len(node_ids)
        when some nodes carry no embedding yet).
    """
    if not node_ids:
        return 0
    await reconciler.reconcile_in_session(session)
    rows = await select_embedded_nodes(session, skip=0, limit=len(node_ids), node_ids=node_ids)
    if not rows:
        return 0
    return await _upsert_rows(index, rows)
