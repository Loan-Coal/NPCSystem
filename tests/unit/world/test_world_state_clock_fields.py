"""
Unit tests for ISSUE-165: WorldState carries the persisted game clock.

Covers the model fields, the monotonic MERGE guard, the narrow persist_clock_state
writer, and GameClock.restore. No I/O — the Neo4j session is a recording stub.
"""

from __future__ import annotations

import asyncio
from typing import Any

from npc_engine.graph.world_state.world_state_writer import (
    CYPHER_MERGE_WORLD_STATE,
    CYPHER_SET_WORLD_CLOCK,
    _world_state_from_record,
    _world_state_write_params,
    persist_clock_state,
)
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.world.world_state import (
    DEFAULT_GAME_TIME_SECONDS,
    DEFAULT_TICK_ID,
    WorldState,
)


class _RecordingSession:
    """Captures the Cypher query and params passed to run()."""

    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any]]] = []

    async def run(self, query: str, **params: Any) -> None:
        self.queries.append((query, params))


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_world_state_defaults_to_tick_zero():
    """A fresh world starts at tick 0 with 0 elapsed game seconds."""
    state = WorldState(id="world")
    assert state.tick_id == DEFAULT_TICK_ID == 0
    assert state.game_time_seconds == DEFAULT_GAME_TIME_SECONDS == 0


def test_world_state_carries_clock_fields():
    """Clock fields round-trip through the frozen model."""
    state = WorldState(id="world", tick_id=17, game_time_seconds=340)
    assert state.tick_id == 17
    assert state.game_time_seconds == 340


# ---------------------------------------------------------------------------
# Monotonic MERGE guard
# ---------------------------------------------------------------------------


def test_merge_query_guards_tick_monotonicity():
    """The MERGE must never lower a stored tick — stale snapshot writers exist."""
    assert "w.tick_id = CASE WHEN" in CYPHER_MERGE_WORLD_STATE
    assert "w.game_time_seconds = CASE WHEN" in CYPHER_MERGE_WORLD_STATE
    # No inline literals: defaults arrive as bound params.
    assert "$default_tick_id" in CYPHER_MERGE_WORLD_STATE
    assert "$default_game_time_seconds" in CYPHER_MERGE_WORLD_STATE


def test_write_params_include_clock_and_defaults():
    """The param map must supply both the values and the coalesce defaults."""
    params = _world_state_write_params(WorldState(id="world", tick_id=9, game_time_seconds=88))
    assert params["tick_id"] == 9
    assert params["game_time_seconds"] == 88
    assert params["default_tick_id"] == DEFAULT_TICK_ID
    assert params["default_game_time_seconds"] == DEFAULT_GAME_TIME_SECONDS


def test_from_record_reads_clock_fields():
    """Confirmed graph values win over the fallback model."""
    result = _world_state_from_record(
        {"id": "world", "tick_id": 42, "game_time_seconds": 500},
        WorldState(id="world", tick_id=1, game_time_seconds=2),
    )
    assert result.tick_id == 42
    assert result.game_time_seconds == 500


def test_from_record_falls_back_when_props_absent():
    """A pre-ISSUE-165 node has no clock props; fall back rather than crash."""
    result = _world_state_from_record({"id": "world"}, WorldState(id="world", tick_id=7, game_time_seconds=8))
    assert result.tick_id == 7
    assert result.game_time_seconds == 8


# ---------------------------------------------------------------------------
# Narrow clock writer
# ---------------------------------------------------------------------------


def test_persist_clock_state_writes_only_clock_fields():
    """The scheduler holds a stale WorldState snapshot; the write must stay narrow."""
    session = _RecordingSession()
    asyncio.run(persist_clock_state(session, world_id="world", tick_id=5, game_time_seconds=50))

    query, params = session.queries[0]
    assert query == CYPHER_SET_WORLD_CLOCK
    assert params["world_id"] == "world"
    assert params["tick_id"] == 5
    assert params["game_time_seconds"] == 50
    for clobbered in ("epoch", "weather", "faction_standings", "active_conditions"):
        assert clobbered not in query


def test_persist_clock_state_query_is_monotonic():
    """Same guard as the full MERGE — event emission is unordered w.r.t. finalize."""
    assert "CASE WHEN" in CYPHER_SET_WORLD_CLOCK
    assert "$default_tick_id" in CYPHER_SET_WORLD_CLOCK


# ---------------------------------------------------------------------------
# GameClock.restore
# ---------------------------------------------------------------------------


def test_restore_seeds_a_fresh_clock():
    """Startup hydration lifts a fresh clock to the persisted tick."""
    clock = GameClock(mode="game_driven")
    state = asyncio.run(clock.restore(tick_id=12, game_time_seconds=120))
    assert state.tick_id == 12
    assert clock.current_tick == 12
    assert state.game_time_seconds == 120


def test_restore_never_rewinds_a_running_clock():
    """A late or duplicate restore must not move the clock backwards."""
    clock = GameClock(mode="game_driven")
    asyncio.run(clock.advance(tick_delta=20, time_delta_seconds=200))
    asyncio.run(clock.restore(tick_id=3, game_time_seconds=30))
    assert clock.current_tick == 20
    assert clock.state.game_time_seconds == 200


def test_restore_of_absent_world_is_a_noop():
    """get_world_state returns a default (tick 0) when the node is missing."""
    clock = GameClock(mode="game_driven")
    asyncio.run(clock.advance(tick_delta=4, time_delta_seconds=0))
    asyncio.run(clock.restore(tick_id=0, game_time_seconds=0))
    assert clock.current_tick == 4
