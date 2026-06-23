"""
test_director_tick.py - Unit tests for the DirectorTick scheduler adapter (F1.5).

Drives run_tick with injected read ports (fake PlayerLocationReadPort + RelationReadPort)
and a spy EventHandler. No real Neo4j is touched. The director keeps receiving a session
only to forward to the event handler (events not yet migrated — DEC-122 / SEV-24).

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

from npc_engine.engines.director.director_tick import DirectorTick
from npc_engine.utils.errors import RelationEdgeNotFoundError


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeLocationReader:
    """PlayerLocationReadPort double: fixed pairs + a configurable idle count."""

    def __init__(self, pairs: list[tuple[str, str]], idle: int = 0) -> None:
        self._pairs = pairs
        self._idle = idle

    async def get_collocated_pairs(self) -> list[tuple[str, str]]:
        return self._pairs

    async def get_player_idle_ticks(
        self, *, npc_id: str, player_id: str, tick_id: int
    ) -> int:
        return self._idle


class _FakeRelationReader:
    """RelationReadPort double: returns neutral-ish scalars for all pairs."""

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        return {"trust": 5, "fear": 0, "affection": 5}


class _MissingRelationReader:
    """RelationReadPort double that always raises (absent RELATES_TO edge)."""

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)


class _SpyEventHandler:
    """Records run_tick calls; returns a stub event dict."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run_tick(self, *, tick_id: int, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"tick_id": tick_id})
        return {"events": [{"id": "evt-1"}]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_fires_event_and_returns_beat() -> None:
    """High idle count triggers decide() → event_handler.run_tick called once; beat returned."""
    # idle=15 > IDLE_INJECT_THRESHOLD_TICKS (10) → re_engage_idle decision
    spy_handler = _SpyEventHandler()

    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_a", "player_1")], idle=15),
        relation_reader=_FakeRelationReader(),
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(tick_id=5)

    assert len(result["director_beats"]) == 1
    beat = result["director_beats"][0]
    assert beat["beat_kind"] == "re_engage_idle"
    assert beat["npc_id"] == "npc_a"
    assert beat["player_id"] == "player_1"
    assert "event" in beat
    assert len(spy_handler.calls) == 1


@pytest.mark.asyncio
async def test_fired_beat_recorded_in_beat_log() -> None:
    """When a beat fires and a beat log is injected, the beat is recorded (F2.4)."""
    from npc_engine.engines.director.director_beat_log import DirectorBeatLog

    beat_log = DirectorBeatLog()

    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_a", "player_1")], idle=15),
        relation_reader=_FakeRelationReader(),
        event_handler=_SpyEventHandler(),
        beat_log=beat_log,
    )
    await adapter.run_tick(tick_id=5)

    recent = beat_log.recent(limit=5)
    assert len(recent) == 1
    assert recent[0].beat_kind == "re_engage_idle"
    assert recent[0].npc_id == "npc_a"
    assert recent[0].tick == 5


@pytest.mark.asyncio
async def test_no_decision_below_threshold_no_event() -> None:
    """Low idle + NEUTRAL standing → decide() returns None → no event, empty beats."""
    # idle=3 < threshold=10 → no decision from re_engage_idle; NEUTRAL → no tension_escalation
    spy_handler = _SpyEventHandler()

    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_a", "player_1")], idle=3),
        relation_reader=_FakeRelationReader(),
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(tick_id=5)

    assert result["director_beats"] == []
    assert spy_handler.calls == []


@pytest.mark.asyncio
async def test_missing_edge_defaults_neutral_no_crash() -> None:
    """RelationEdgeNotFoundError → Standing.NEUTRAL fallback; with low idle no decision, no crash."""
    spy_handler = _SpyEventHandler()

    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_b", "player_1")], idle=3),
        relation_reader=_MissingRelationReader(),
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(tick_id=7)

    # NEUTRAL standing + idle=3 < threshold → no beat, no event, no crash
    assert result["director_beats"] == []
    assert spy_handler.calls == []


@pytest.mark.asyncio
async def test_plateau_tracker_increments_when_standing_unchanged() -> None:
    """ISSUE-097: consecutive ticks at the same Standing band increment the plateau counter."""
    from npc_engine.engines.director.director_engine import PLATEAU_INJECT_THRESHOLD_TICKS

    # relationship_catalyst fires when plateau_ticks > PLATEAU_INJECT_THRESHOLD_TICKS (20).
    # idle=0 (no idle beat), standing=NEUTRAL.
    # After PLATEAU_INJECT_THRESHOLD_TICKS+1 ticks the plateau counter crosses threshold.
    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_c", "player_1")], idle=0),
        relation_reader=_FakeRelationReader(),  # NEUTRAL scalars
        event_handler=_SpyEventHandler(),
    )

    for tick in range(PLATEAU_INJECT_THRESHOLD_TICKS + 2):
        result = await adapter.run_tick(tick_id=tick)

    # After enough ticks without Standing change, relationship_catalyst must fire.
    beats = result["director_beats"]
    assert len(beats) == 1
    assert beats[0]["beat_kind"] == "relationship_catalyst"


@pytest.mark.asyncio
async def test_plateau_tracker_resets_on_standing_change() -> None:
    """ISSUE-097: plateau counter resets when Standing band changes."""
    from npc_engine.engines.director.director_engine import PLATEAU_INJECT_THRESHOLD_TICKS

    class _AlternatingReader:
        """Standing alternates between NEUTRAL and ALLIED every call to prevent accumulation."""
        _call_count = 0

        async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
            self._call_count += 1
            # Alternate between NEUTRAL (low affection) and ALLIED (high affection/trust)
            if self._call_count % 2 == 0:
                return {"trust": 5, "fear": 0, "affection": 5}   # NEUTRAL
            return {"trust": 90, "fear": 0, "affection": 90}     # ALLIED

    spy = _SpyEventHandler()
    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_d", "player_1")], idle=0),
        relation_reader=_AlternatingReader(),
        event_handler=spy,
    )

    for tick in range(PLATEAU_INJECT_THRESHOLD_TICKS + 5):
        result = await adapter.run_tick(tick_id=tick)

    # Standing alternates every tick → plateau never accumulates → no relationship_catalyst
    beats = result["director_beats"]
    assert not any(b["beat_kind"] == "relationship_catalyst" for b in beats)


@pytest.mark.asyncio
async def test_missing_edge_hostile_still_fires_when_triggered() -> None:
    """If the engine would decide on HOSTILE, but edge is missing default NEUTRAL prevents it."""
    # With missing edge and idle=3: NEUTRAL derived, no HOSTILE trigger, no beat.
    # This verifies the default-NEUTRAL path doesn't accidentally trigger beats.
    spy_handler = _SpyEventHandler()

    adapter = DirectorTick(
        location_reader=_FakeLocationReader([("npc_c", "player_1")], idle=3),
        relation_reader=_MissingRelationReader(),
        event_handler=spy_handler,
    )
    result = await adapter.run_tick(tick_id=2)

    assert result["director_beats"] == []
