"""
test_tick_scheduler_engine_isolation.py - Unit tests for per-engine error isolation.

Verifies that a throwing engine does not kill the tick loop and that errors
are recorded in the EngineStatusStore.

Does NOT: exercise real Neo4j or LLM calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def single(self) -> dict[str, Any] | None:
        return self._row

    async def consume(self) -> None:
        pass


class _FakeSession:
    async def run(self, query: str, **kwargs) -> _FakeResult:
        if "WorldState" in query:
            return _FakeResult(None)
        return _FakeResult({"done": False})


class _GoodEngine:
    """Records successful run_tick calls."""

    def __init__(self) -> None:
        self.tick_ids: list[int] = []

    async def run_tick(self, *, tick_id: int, **kwargs: Any) -> dict:
        self.tick_ids.append(tick_id)
        return {"tick_id": tick_id}


class _ThrowingEngine:
    """Always raises on run_tick."""

    async def run_tick(self, *, tick_id: int, **kwargs: Any) -> dict:
        raise ValueError("deliberate engine failure")


def _make_scheduler(
    *,
    gossip_engine: Any = None,
    event_engine: Any = None,
    story_pacing_engine: Any = None,
    routine_engine: Any = None,
    faction_politics_engine: Any = None,
    status_store: EngineStatusStore | None = None,
) -> TickScheduler:
    clock = GameClock(mode="game_driven")
    return TickScheduler(
        clock=clock,
        gossip_handler=gossip_engine or _GoodEngine(),
        event_handler=event_engine or _GoodEngine(),
        gossip_interval=1,
        event_interval=1,
        story_pacing_engine=story_pacing_engine,
        routine_engine=routine_engine,
        faction_politics_engine=faction_politics_engine,
        engine_status_store=status_store,
    )


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_throwing_gossip_does_not_stop_event_engine() -> None:
    gossip = _ThrowingEngine()
    event = _GoodEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event)
    await scheduler.advance(session=_FakeSession(), tick_delta=3, time_delta_seconds=0)
    assert event.tick_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_throwing_event_does_not_stop_gossip_engine() -> None:
    gossip = _GoodEngine()
    event = _ThrowingEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event)
    await scheduler.advance(session=_FakeSession(), tick_delta=3, time_delta_seconds=0)
    assert gossip.tick_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_throwing_optional_engine_does_not_stop_gossip() -> None:
    gossip = _GoodEngine()
    event = _GoodEngine()
    throwing_fp = _ThrowingEngine()
    scheduler = _make_scheduler(
        gossip_engine=gossip,
        event_engine=event,
        faction_politics_engine=throwing_fp,
    )
    await scheduler.advance(session=_FakeSession(), tick_delta=2, time_delta_seconds=0)
    assert gossip.tick_ids == [1, 2]
    assert event.tick_ids == [1, 2]


@pytest.mark.asyncio
async def test_throwing_story_pacing_does_not_stop_other_engines() -> None:
    gossip = _GoodEngine()
    event = _GoodEngine()
    throwing_sp = _ThrowingEngine()
    scheduler = _make_scheduler(
        gossip_engine=gossip,
        event_engine=event,
        story_pacing_engine=throwing_sp,
    )
    await scheduler.advance(session=_FakeSession(), tick_delta=2, time_delta_seconds=0)
    assert gossip.tick_ids == [1, 2]
    assert event.tick_ids == [1, 2]


# ---------------------------------------------------------------------------
# Status store recording
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_recorded_in_status_store() -> None:
    store = EngineStatusStore()
    gossip = _ThrowingEngine()
    event = _GoodEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event, status_store=store)
    await scheduler.advance(session=_FakeSession(), tick_delta=1, time_delta_seconds=0)
    record = store.get("gossip")
    assert record is not None
    assert record.last_error == "deliberate engine failure"
    assert record.last_error_tick == 1
    assert record.error_count == 1


@pytest.mark.asyncio
async def test_success_recorded_in_status_store() -> None:
    store = EngineStatusStore()
    gossip = _GoodEngine()
    event = _GoodEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event, status_store=store)
    await scheduler.advance(session=_FakeSession(), tick_delta=2, time_delta_seconds=0)
    record = store.get("gossip")
    assert record is not None
    assert record.last_tick_id == 2
    assert record.last_error is None


@pytest.mark.asyncio
async def test_error_count_accumulates_across_ticks() -> None:
    store = EngineStatusStore()
    gossip = _ThrowingEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, status_store=store)
    await scheduler.advance(session=_FakeSession(), tick_delta=3, time_delta_seconds=0)
    record = store.get("gossip")
    assert record is not None
    assert record.error_count == 3


@pytest.mark.asyncio
async def test_status_store_is_optional() -> None:
    """Scheduler works correctly when no status_store is provided."""
    gossip = _ThrowingEngine()
    event = _GoodEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event, status_store=None)
    # Must not raise even with no store and a throwing engine
    await scheduler.advance(session=_FakeSession(), tick_delta=1, time_delta_seconds=0)
    assert event.tick_ids == [1]


# ---------------------------------------------------------------------------
# engine_status property
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_status_property_returns_dict() -> None:
    store = EngineStatusStore()
    gossip = _GoodEngine()
    event = _ThrowingEngine()
    scheduler = _make_scheduler(gossip_engine=gossip, event_engine=event, status_store=store)
    await scheduler.advance(session=_FakeSession(), tick_delta=1, time_delta_seconds=0)
    status = scheduler.engine_status
    assert "gossip" in status
    assert status["gossip"]["last_tick_id"] == 1
    assert "event" in status
    assert status["event"]["last_error"] == "deliberate engine failure"


@pytest.mark.asyncio
async def test_engine_status_empty_when_no_store() -> None:
    scheduler = _make_scheduler(status_store=None)
    assert scheduler.engine_status == {}


# ---------------------------------------------------------------------------
# Interval cadence (characterization tests for advance() refactor)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gossip_runs_only_on_interval_ticks() -> None:
    gossip = _GoodEngine()
    event = _GoodEngine()
    clock = GameClock(mode="game_driven")
    scheduler = TickScheduler(
        clock=clock,
        gossip_handler=gossip,
        event_handler=event,
        gossip_interval=3,
        event_interval=1,
    )
    await scheduler.advance(session=_FakeSession(), tick_delta=6, time_delta_seconds=0)
    assert gossip.tick_ids == [3, 6]
    assert event.tick_ids == [1, 2, 3, 4, 5, 6]


@pytest.mark.asyncio
async def test_event_runs_only_on_interval_ticks() -> None:
    gossip = _GoodEngine()
    event = _GoodEngine()
    clock = GameClock(mode="game_driven")
    scheduler = TickScheduler(
        clock=clock,
        gossip_handler=gossip,
        event_handler=event,
        gossip_interval=1,
        event_interval=4,
    )
    await scheduler.advance(session=_FakeSession(), tick_delta=8, time_delta_seconds=0)
    assert event.tick_ids == [4, 8]
    assert gossip.tick_ids == [1, 2, 3, 4, 5, 6, 7, 8]
