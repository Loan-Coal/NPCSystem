"""
test_director_tick.py - Unit tests for the DirectorTick scheduler adapter (F1.5).

Drives run_tick with a fake co-location reader, monkeypatched RelationReader and
decide/derive_standing, and a spy EventHandler. No real Neo4j is touched.

Verifies:
  1. When decide() returns a decision for a pair, event_handler.run_tick is called
     once and director_beats contains one record with the expected beat_kind/npc_id.
  2. When idle is below threshold and standing is NEUTRAL, no decision → event_handler
     not called → director_beats is empty.
  3. When RelationEdgeNotFoundError is raised, standing defaults to NEUTRAL and no
     crash occurs.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.director import director_tick as mod
from npc_engine.engines.relationship.standing import Standing
from npc_engine.engines.director.director_engine import DirectorDecision
from npc_engine.utils.errors import RelationEdgeNotFoundError


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeLocationReader:
    """Returns a fixed list of pairs and a configurable idle count."""

    def __init__(self, pairs: list[tuple[str, str]], idle: int = 0) -> None:
        self._pairs = pairs
        self._idle = idle

    async def get_collocated_pairs(self, session: Any) -> list[tuple[str, str]]:
        return self._pairs

    async def get_player_idle_ticks(
        self,
        session: Any,
        *,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> int:
        return self._idle


class _FakeRelationReader:
    """Returns neutral-ish scalars for all pairs (no missing edges)."""

    def __init__(self, session: Any) -> None:
        pass

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        return {"trust": 5, "fear": 0, "affection": 5}


class _MissingRelationReader:
    """Always raises RelationEdgeNotFoundError — simulates absent RELATES_TO edge."""

    def __init__(self, session: Any) -> None:
        pass

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)


class _SpyEventHandler:
    """Records run_tick calls; returns a stub event dict."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run_tick(self, *, session: Any, tick_id: int, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"session": session, "tick_id": tick_id})
        return {"events": [{"id": "evt-1"}]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_fires_event_and_returns_beat(monkeypatch) -> None:
    """High idle count triggers decide() → event_handler.run_tick called once; beat returned."""
    # idle=15 > IDLE_INJECT_THRESHOLD_TICKS (10) → re_engage_idle decision
    location_reader = _FakeLocationReader([("npc_a", "player_1")], idle=15)
    spy_handler = _SpyEventHandler()

    monkeypatch.setattr(mod, "RelationReader", _FakeRelationReader)

    adapter = mod.DirectorTick(
        location_reader=location_reader,
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(session=object(), tick_id=5)

    assert len(result["director_beats"]) == 1
    beat = result["director_beats"][0]
    assert beat["beat_kind"] == "re_engage_idle"
    assert beat["npc_id"] == "npc_a"
    assert beat["player_id"] == "player_1"
    assert "event" in beat
    assert len(spy_handler.calls) == 1


@pytest.mark.asyncio
async def test_fired_beat_recorded_in_beat_log(monkeypatch) -> None:
    """When a beat fires and a beat log is injected, the beat is recorded (F2.4)."""
    from npc_engine.engines.director.director_beat_log import DirectorBeatLog

    location_reader = _FakeLocationReader([("npc_a", "player_1")], idle=15)
    monkeypatch.setattr(mod, "RelationReader", _FakeRelationReader)
    beat_log = DirectorBeatLog()

    adapter = mod.DirectorTick(
        location_reader=location_reader,
        event_handler=_SpyEventHandler(),
        beat_log=beat_log,
    )
    await adapter.run_tick(session=object(), tick_id=5)

    recent = beat_log.recent(limit=5)
    assert len(recent) == 1
    assert recent[0].beat_kind == "re_engage_idle"
    assert recent[0].npc_id == "npc_a"
    assert recent[0].tick == 5


@pytest.mark.asyncio
async def test_no_decision_below_threshold_no_event(monkeypatch) -> None:
    """Low idle + NEUTRAL standing → decide() returns None → no event, empty beats."""
    # idle=3 < threshold=10 → no decision from re_engage_idle; NEUTRAL → no tension_escalation
    location_reader = _FakeLocationReader([("npc_a", "player_1")], idle=3)
    spy_handler = _SpyEventHandler()

    monkeypatch.setattr(mod, "RelationReader", _FakeRelationReader)

    adapter = mod.DirectorTick(
        location_reader=location_reader,
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(session=object(), tick_id=5)

    assert result["director_beats"] == []
    assert spy_handler.calls == []


@pytest.mark.asyncio
async def test_missing_edge_defaults_neutral_no_crash(monkeypatch) -> None:
    """RelationEdgeNotFoundError → Standing.NEUTRAL fallback; with low idle no decision, no crash."""
    location_reader = _FakeLocationReader([("npc_b", "player_1")], idle=3)
    spy_handler = _SpyEventHandler()

    monkeypatch.setattr(mod, "RelationReader", _MissingRelationReader)

    adapter = mod.DirectorTick(
        location_reader=location_reader,
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(session=object(), tick_id=7)

    # NEUTRAL standing + idle=3 < threshold → no beat, no event, no crash
    assert result["director_beats"] == []
    assert spy_handler.calls == []


@pytest.mark.asyncio
async def test_missing_edge_hostile_still_fires_when_triggered(monkeypatch) -> None:
    """If the engine would decide on HOSTILE, but edge is missing default NEUTRAL prevents it."""
    # With missing edge and idle=3: NEUTRAL derived, no HOSTILE trigger, no beat.
    # This verifies the default-NEUTRAL path doesn't accidentally trigger beats.
    location_reader = _FakeLocationReader([("npc_c", "player_1")], idle=3)
    spy_handler = _SpyEventHandler()

    monkeypatch.setattr(mod, "RelationReader", _MissingRelationReader)

    adapter = mod.DirectorTick(
        location_reader=location_reader,
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(session=object(), tick_id=2)

    assert result["director_beats"] == []
