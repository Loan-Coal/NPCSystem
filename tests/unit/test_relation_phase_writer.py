"""
test_relation_phase_writer.py - Unit tests for write_relationship_phase graph writer.

Does NOT: execute real Neo4j I/O.

Dependencies injected: None (stub AsyncSession).
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FakeResult:
    """Stub Neo4j result that records consumed state."""

    def __init__(self) -> None:
        self._consumed = False

    async def consume(self) -> "_FakeSummary":
        self._consumed = True
        return _FakeSummary()


class _FakeSummary:
    """Stub Neo4j summary with a counters object."""

    class _Counters:
        properties_set: int = 2

    counters = _Counters()


class _FakeTx:
    """Stub Neo4j AsyncTransaction that captures the last run call."""

    def __init__(self) -> None:
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.last_query = query
        self.last_params = params
        return _FakeResult()

    async def commit(self) -> None:
        pass

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakeSession:
    """Stub Neo4j AsyncSession that returns _FakeTx from begin_transaction."""

    def __init__(self) -> None:
        self.tx = _FakeTx()

    async def begin_transaction(self) -> _FakeTx:
        return self.tx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_writes_phase_fields() -> None:
    """write_relationship_phase sets relationship_phase and phase_started_at_tick."""
    from npc_engine.engines.relationship.affinity_engine import RelationshipPhase
    from npc_engine.graph.relation_phase_writer import write_relationship_phase

    session = _FakeSession()
    await write_relationship_phase(
        session=session,
        src_id="npc_a",
        dst_id="npc_b",
        phase=RelationshipPhase.FRIEND,
        tick=15,
    )

    params = session.tx.last_params
    assert params["relationship_phase"] == RelationshipPhase.FRIEND.value
    assert params["phase_started_at_tick"] == 15
    assert params["src_id"] == "npc_a"
    assert params["dst_id"] == "npc_b"


@pytest.mark.asyncio
async def test_cypher_targets_relates_to_edge() -> None:
    """write_relationship_phase Cypher query targets the RELATES_TO edge."""
    from npc_engine.engines.relationship.affinity_engine import RelationshipPhase
    from npc_engine.graph.relation_phase_writer import write_relationship_phase

    session = _FakeSession()
    await write_relationship_phase(
        session=session,
        src_id="npc_x",
        dst_id="npc_y",
        phase=RelationshipPhase.HOSTILE,
        tick=1,
    )

    assert "RELATES_TO" in session.tx.last_query
    assert "relationship_phase" in session.tx.last_query
    assert "phase_started_at_tick" in session.tx.last_query
