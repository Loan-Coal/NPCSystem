"""
test_embedding_reconciler.py - Unit tests for embedding reconciler stale-index healing.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: None.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from npc_engine.retrieval.embedding_reconciler import EmbeddingReconciler


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


class _EmbeddingIndexStub:
    def __init__(self, fail_on_id: str | None = None):
        self.fail_on_id = fail_on_id
        self.upserts: list[tuple[str, str, dict]] = []

    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        if self.fail_on_id == item_id:
            raise RuntimeError("forced upsert failure")
        self.upserts.append((item_id, text, payload))


@pytest.mark.asyncio
async def test_reconcile_once_upserts_and_marks_rows() -> None:
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
    assert [entry[0] for entry in index.upserts] == ["npc_1", "event_1"]
    assert all("indexed_at" in entry[2] for entry in index.upserts)
    mark_calls = [call for call in session.run_calls if call[0].startswith("MATCH (n:Character") or call[0].startswith("MATCH (n:Event")]
    assert len(mark_calls) == 2


@pytest.mark.asyncio
async def test_reconcile_once_continues_after_single_row_failure() -> None:
    session = _SessionStub(
        rows=[
            _NodeRow(id="npc_fail", kind="Character", text="Broken row", payload={}),
            _NodeRow(id="loc_1", kind="Location", text="North gate", payload={"name": "North Gate"}),
        ]
    )
    graph_db = _GraphDbStub(session=session)
    index = _EmbeddingIndexStub(fail_on_id="npc_fail")
    reconciler = EmbeddingReconciler(graph_db=graph_db, embedding_index=index, interval_seconds=300)

    result = await reconciler.reconcile_once()

    assert result["processed"] == 1
    assert result["failed"] == 1
    assert [entry[0] for entry in index.upserts] == ["loc_1"]


@pytest.mark.asyncio
async def test_reconcile_once_noops_when_no_stale_rows() -> None:
    session = _SessionStub(rows=[])
    graph_db = _GraphDbStub(session=session)
    index = _EmbeddingIndexStub()
    reconciler = EmbeddingReconciler(graph_db=graph_db, embedding_index=index, interval_seconds=300)

    result = await reconciler.reconcile_once()

    assert result == {"processed": 0, "failed": 0}
    assert index.upserts == []


def test_stale_nodes_query_excludes_inactive_characters() -> None:
    """Reconciler query must filter inactive Characters at the DB level."""

    from npc_engine.retrieval.embedding_reconciler import CYPHER_SELECT_STALE_NODES

    character_block = CYPHER_SELECT_STALE_NODES.split("UNION")[0]
    assert "n.is_active = true" in character_block, (
        "Character branch of reconciler query must require is_active = true"
    )

    event_block = CYPHER_SELECT_STALE_NODES.split("UNION")[1]
    assert "n.is_active" not in event_block, (
        "Event branch must not filter by is_active (Events have no such field)"
    )
