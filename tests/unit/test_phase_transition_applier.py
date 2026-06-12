"""
test_phase_transition_applier.py - Unit tests for apply_phase_transition.

Verifies the read -> derive -> conditional-write orchestration without real I/O
by monkeypatching the graph reader and writer the applier depends on.

Dependencies injected: monkeypatched get_relation_phase_state / write_relationship_phase.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.relationship import phase_transition_applier as mod
from npc_engine.engines.relationship.affinity_engine import RelationshipPhase
from npc_engine.graph.relation_phase_reader import RelationPhaseRow


def _patch_reader(monkeypatch, row: RelationPhaseRow | None) -> None:
    async def _fake_reader(*, session: Any, src_id: str, dst_id: str) -> RelationPhaseRow | None:
        return row

    monkeypatch.setattr(mod, "get_relation_phase_state", _fake_reader)


def _patch_writer(monkeypatch, captured: dict[str, Any]) -> None:
    async def _fake_writer(*, session: Any, src_id: str, dst_id: str, phase: str, tick: int) -> None:
        captured.update({"src_id": src_id, "dst_id": dst_id, "phase": phase, "tick": tick})

    monkeypatch.setattr(mod, "write_relationship_phase", _fake_writer)


@pytest.mark.asyncio
async def test_writes_phase_on_transition(monkeypatch) -> None:
    """A composite score crossing a band boundary persists the new phase."""
    # trust+affection-fear = 90 -> CLOSE; current STRANGER -> transition expected.
    _patch_reader(monkeypatch, RelationPhaseRow(trust=50, fear=0, affection=40, relationship_phase="STRANGER"))
    captured: dict[str, Any] = {}
    _patch_writer(monkeypatch, captured)

    transition = await mod.apply_phase_transition(session=object(), src_id="npc_a", dst_id="player_1", tick=42)

    assert transition is not None
    assert transition.new_phase is RelationshipPhase.CLOSE
    assert captured == {"src_id": "npc_a", "dst_id": "player_1", "phase": "CLOSE", "tick": 42}


@pytest.mark.asyncio
async def test_no_write_when_phase_unchanged(monkeypatch) -> None:
    """When the derived phase equals the current phase, nothing is written."""
    # score 0 -> STRANGER; current STRANGER -> no transition.
    _patch_reader(monkeypatch, RelationPhaseRow(trust=0, fear=0, affection=0, relationship_phase="STRANGER"))
    captured: dict[str, Any] = {}
    _patch_writer(monkeypatch, captured)

    transition = await mod.apply_phase_transition(session=object(), src_id="npc_a", dst_id="player_1", tick=7)

    assert transition is None
    assert captured == {}


@pytest.mark.asyncio
async def test_null_phase_treated_as_stranger(monkeypatch) -> None:
    """A never-transitioned edge (null phase) is compared against STRANGER baseline."""
    # score 0 -> STRANGER, baseline STRANGER -> no transition despite null stored phase.
    _patch_reader(monkeypatch, RelationPhaseRow(trust=10, fear=10, affection=0, relationship_phase=None))
    captured: dict[str, Any] = {}
    _patch_writer(monkeypatch, captured)

    transition = await mod.apply_phase_transition(session=object(), src_id="npc_a", dst_id="player_1", tick=3)

    assert transition is None
    assert captured == {}


@pytest.mark.asyncio
async def test_no_edge_returns_none(monkeypatch) -> None:
    """When no RELATES_TO edge exists, the applier is a no-op returning None."""
    _patch_reader(monkeypatch, None)
    captured: dict[str, Any] = {}
    _patch_writer(monkeypatch, captured)

    transition = await mod.apply_phase_transition(session=object(), src_id="npc_a", dst_id="player_1", tick=9)

    assert transition is None
    assert captured == {}
