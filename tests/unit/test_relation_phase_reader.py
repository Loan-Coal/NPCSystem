"""
test_relation_phase_reader.py - Unit tests for get_relation_phase_state graph reader.

Does NOT: execute real Neo4j I/O.

Dependencies injected: None (stub AsyncSession returning a fake record).
"""

from __future__ import annotations

from typing import Any

import pytest


class _FakeRecord:
    """Dict-backed stand-in for a neo4j Record."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> Any:
        return self._values[key]


class _FakeResult:
    """Stub Neo4j result returning a single (or no) record."""

    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record

    async def single(self) -> _FakeRecord | None:
        return self._record


class _FakeTx:
    """Stub AsyncTransaction capturing the query and yielding a preset record."""

    def __init__(self, record: _FakeRecord | None) -> None:
        self._record = record
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.last_query = query
        self.last_params = params
        return _FakeResult(self._record)

    async def commit(self) -> None:
        pass

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakeSession:
    """Stub AsyncSession returning a _FakeTx from begin_transaction."""

    def __init__(self, record: _FakeRecord | None) -> None:
        self.tx = _FakeTx(record)

    async def begin_transaction(self) -> _FakeTx:
        return self.tx


@pytest.mark.asyncio
async def test_returns_scalars_and_phase() -> None:
    """get_relation_phase_state maps the record into a RelationPhaseRow."""
    from npc_engine.graph.relation_phase_reader import get_relation_phase_state

    record = _FakeRecord({"trust": 30, "fear": 5, "affection": 40, "relationship_phase": "ACQUAINTANCE", "phase_started_at_tick": 7})
    session = _FakeSession(record)

    row = await get_relation_phase_state(session=session, src_id="npc_a", dst_id="player_1")

    assert row is not None
    assert row.trust == 30
    assert row.fear == 5
    assert row.affection == 40
    assert row.relationship_phase == "ACQUAINTANCE"
    assert row.phase_started_at_tick == 7
    assert session.tx.last_params == {"src_id": "npc_a", "dst_id": "player_1"}
    assert "RELATES_TO" in session.tx.last_query


@pytest.mark.asyncio
async def test_returns_none_when_no_edge() -> None:
    """get_relation_phase_state returns None when no RELATES_TO edge exists."""
    from npc_engine.graph.relation_phase_reader import get_relation_phase_state

    session = _FakeSession(None)

    row = await get_relation_phase_state(session=session, src_id="npc_a", dst_id="player_1")

    assert row is None


@pytest.mark.asyncio
async def test_phase_defaults_to_none_when_unset() -> None:
    """A null relationship_phase property is surfaced as None (never-transitioned edge)."""
    from npc_engine.graph.relation_phase_reader import get_relation_phase_state

    record = _FakeRecord({"trust": 0, "fear": 0, "affection": 0, "relationship_phase": None, "phase_started_at_tick": None})
    session = _FakeSession(record)

    row = await get_relation_phase_state(session=session, src_id="npc_a", dst_id="player_1")

    assert row is not None
    assert row.relationship_phase is None
