"""
test_embedding_reconciler.py - Unit tests for embedding reconciler stale-index healing.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: None.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest

from npc_engine.retrieval.embedding_reconciler import EmbeddingReconciler

EMBED_DIM = 4  # small dimension for test vectors


@dataclass(frozen=True)
class _NodeRow:
    id: str
    kind: str
    text: str
    payload: dict


class _ResultStub:
    def __init__(self, rows: list[_NodeRow]):
        self._rows = rows

    def __aiter__(self) -> AsyncIterator[dict]:
        async def _iterator() -> AsyncIterator[dict]:
            for row in self._rows:
                yield {
                    "id": row.id,
                    "kind": row.kind,
                    "text": row.text,
                    "payload": row.payload,
                }

        return _iterator()

    async def consume(self) -> None:
        pass


class _SessionStub:
    def __init__(self, rows: list[_NodeRow]):
        self.rows = rows
        self.run_calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params):
        self.run_calls.append((query, params))
        normalized_query = query.strip()
        if "RETURN n.id AS id" in normalized_query:
            return _ResultStub(rows=self.rows)
        return _ResultStub(rows=[])


class _GraphDbStub:
    def __init__(self, session: _SessionStub):
        self._session = session

    @asynccontextmanager
    async def get_session(self):
        yield self._session


@dataclass
class _EmbeddingIndexStub:
    """Stub embedding index that supports embed_batch (SEV-29 batch API)."""

    fail_on_id: str | None = None
    # Track embed_batch calls
    embed_batch_calls: list[list[str]] = field(default_factory=list)
    # Keep upserts for backward compat (even though reconciler no longer calls upsert)
    upserts: list[tuple[str, str, dict]] = field(default_factory=list)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one fixed-length vector per text."""
        self.embed_batch_calls.append(texts)
        return [[float(i % 10)] * EMBED_DIM for i in range(len(texts))]

    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        if self.fail_on_id == item_id:
            raise RuntimeError("forced upsert failure")
        self.upserts.append((item_id, text, payload))


@pytest.mark.asyncio
async def test_reconcile_once_batch_encodes_and_marks_rows() -> None:
    """reconcile_once must call embed_batch once and mark nodes as indexed."""
    session = _SessionStub(
        rows=[
            _NodeRow(id="npc_1", kind="Character", text="Guard in plaza", payload={"name": "Ari"}),
            _NodeRow(id="event_1", kind="Event", text="Market fire", payload={"summary": "Fire"}),
        ]
    )
    graph_db = _GraphDbStub(session=session)
    index = _EmbeddingIndexStub()
    reconciler = EmbeddingReconciler(graph_db=graph_db, embedding_index=index, interval_seconds=300)

    result = await reconciler.reconcile_once()

    assert result["processed"] == 2
    assert result["failed"] == 0
    # embed_batch called once with both texts
    assert len(index.embed_batch_calls) == 1
    assert set(index.embed_batch_calls[0]) == {"Guard in plaza", "Market fire"}
    # At most 2 session.run calls: 1 SELECT + 1 batch SET
    assert len(session.run_calls) <= 2


@pytest.mark.asyncio
async def test_reconcile_once_noops_when_no_stale_rows() -> None:
    session = _SessionStub(rows=[])
    graph_db = _GraphDbStub(session=session)
    index = _EmbeddingIndexStub()
    reconciler = EmbeddingReconciler(graph_db=graph_db, embedding_index=index, interval_seconds=300)

    result = await reconciler.reconcile_once()

    assert result == {"processed": 0, "failed": 0}
    assert index.embed_batch_calls == []


def test_stale_nodes_query_excludes_inactive_characters() -> None:
    """Reconciler query must filter inactive Characters at the DB level."""

    from npc_engine.graph.embedding_sync_queries import _CYPHER_SELECT_STALE_NODES as CYPHER_SELECT_STALE_NODES

    character_block = CYPHER_SELECT_STALE_NODES.split("UNION")[0]
    assert "n.is_active = true" in character_block, (
        "Character branch of reconciler query must require is_active = true"
    )

    event_block = CYPHER_SELECT_STALE_NODES.split("UNION")[1]
    assert "n.is_active" not in event_block, (
        "Event branch must not filter by is_active (Events have no such field)"
    )
