"""
test_phase_transition_applier.py - Unit tests for apply_phase_transition.

Verifies the read -> derive -> conditional-write orchestration without real I/O
by injecting fake RelationReadPort / RelationPhaseWritePort ports (DEC-122 / SEV-24);
the applier holds no Neo4j session.

Dependencies injected: in-test fake read/write ports.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.relationship import phase_transition_applier as mod
from npc_engine.engines.relationship.affinity_engine import RelationshipPhase
from npc_engine.graph.relations.relation_phase_reader import RelationPhaseRow


class _FakeReader:
    def __init__(self, row: RelationPhaseRow | None) -> None:
        self._row = row

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        raise AssertionError("scalars read not used by applier")

    async def get_relation_phase_row(
        self, *, src_id: str, dst_id: str
    ) -> RelationPhaseRow | None:
        return self._row


class _FakeWriter:
    def __init__(self) -> None:
        self.captured: dict[str, Any] = {}

    async def write_relationship_phase(
        self, *, src_id: str, dst_id: str, phase: str, tick: int
    ) -> None:
        self.captured = {"src_id": src_id, "dst_id": dst_id, "phase": phase, "tick": tick}


@pytest.mark.asyncio
async def test_writes_phase_on_transition() -> None:
    """A composite score crossing a band boundary persists the new phase via the write port."""
    # trust+affection-fear = 90 -> CLOSE; current STRANGER -> transition expected.
    reader = _FakeReader(RelationPhaseRow(trust=50, fear=0, affection=40, relationship_phase="STRANGER"))
    writer = _FakeWriter()

    transition = await mod.apply_phase_transition(
        reader, writer, src_id="npc_a", dst_id="player_1", tick=42
    )

    assert transition is not None
    assert transition.new_phase is RelationshipPhase.CLOSE
    assert writer.captured == {"src_id": "npc_a", "dst_id": "player_1", "phase": "CLOSE", "tick": 42}


@pytest.mark.asyncio
async def test_no_write_when_phase_unchanged() -> None:
    """When the derived phase equals the current phase, the write port is never called."""
    # score 0 -> STRANGER; current STRANGER -> no transition.
    reader = _FakeReader(RelationPhaseRow(trust=0, fear=0, affection=0, relationship_phase="STRANGER"))
    writer = _FakeWriter()

    transition = await mod.apply_phase_transition(
        reader, writer, src_id="npc_a", dst_id="player_1", tick=7
    )

    assert transition is None
    assert writer.captured == {}


@pytest.mark.asyncio
async def test_null_phase_treated_as_stranger() -> None:
    """A never-transitioned edge (null phase) is compared against STRANGER baseline."""
    # score 0 -> STRANGER, baseline STRANGER -> no transition despite null stored phase.
    reader = _FakeReader(RelationPhaseRow(trust=10, fear=10, affection=0, relationship_phase=None))
    writer = _FakeWriter()

    transition = await mod.apply_phase_transition(
        reader, writer, src_id="npc_a", dst_id="player_1", tick=3
    )

    assert transition is None
    assert writer.captured == {}


@pytest.mark.asyncio
async def test_no_edge_returns_none() -> None:
    """When no RELATES_TO edge exists, the applier is a no-op returning None."""
    reader = _FakeReader(None)
    writer = _FakeWriter()

    transition = await mod.apply_phase_transition(
        reader, writer, src_id="npc_a", dst_id="player_1", tick=9
    )

    assert transition is None
    assert writer.captured == {}
