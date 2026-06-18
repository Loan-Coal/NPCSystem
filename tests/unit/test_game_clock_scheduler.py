"""
test_game_clock_scheduler.py - Unit tests for game clock and scheduler trigger logic.

Does NOT: execute real gossip/event handlers.

Dependencies injected: Fake handlers.
"""

import pytest
from typing import Any, cast

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler


class FakeHandler:
    """Captures tick calls for scheduler assertions."""

    def __init__(self):
        self.calls: list[int] = []

    async def run_tick(self, *, tick_id: int, max_pairs: int = 20):
        self.calls.append(tick_id)
        return {"tick_id": tick_id}


class FailingHandler(FakeHandler):
    def __init__(self, fail_on_tick: int):
        super().__init__()
        self._fail_on_tick = fail_on_tick
        self._failed = False

    async def run_tick(self, *, tick_id: int, max_pairs: int = 20):
        if tick_id == self._fail_on_tick and not self._failed:
            self._failed = True
            raise RuntimeError("simulated failure")
        return await super().run_tick(tick_id=tick_id, max_pairs=max_pairs)


class _FakeResult:
    def __init__(self, row: dict[str, Any]):
        self._row = row

    async def single(self):
        return self._row

    async def consume(self) -> None:
        pass


class FakeSession:
    def __init__(self):
        self._state: dict[str, set[int]] = {"gossip_ticks": set(), "event_ticks": set()}

    async def run(self, query: str, **kwargs):
        # WorldState read — return None so get_world_state returns default WorldState
        if "WorldState" in query:
            return _FakeResult(None)
        key = kwargs["key"]
        tick_id = int(kwargs["tick_id"])
        if "RETURN $tick_id IN completed AS done" in query:
            return _FakeResult({"done": tick_id in self._state[key]})
        if "SET s[$key]" in query:
            self._state[key].add(tick_id)
            return _FakeResult({})
        raise AssertionError("Unexpected query")


class FakeLeaseRepo:
    def __init__(self):
        self._done: set[tuple[str, int]] = set()
        self._claims: set[tuple[str, int]] = set()
        self.failed: list[tuple[str, int]] = []

    async def try_claim(self, session, engine: str, tick_id: int) -> bool:
        key = (engine, tick_id)
        if key in self._done or key in self._claims:
            return False
        self._claims.add(key)
        return True

    async def mark_done(self, session, engine: str, tick_id: int) -> bool:
        key = (engine, tick_id)
        if key not in self._claims:
            return False
        self._claims.remove(key)
        self._done.add(key)
        return True

    async def is_done(self, session, engine: str, tick_id: int) -> bool:
        return (engine, tick_id) in self._done

    async def mark_failed(self, session, engine: str, tick_id: int, error: str) -> None:
        key = (engine, tick_id)
        self._claims.discard(key)
        self.failed.append((engine, tick_id))


class FirstTickFailingHandler(FakeHandler):
    def __init__(self):
        super().__init__()
        self._failed_once = False

    async def run_tick(self, *, tick_id: int, max_pairs: int = 20):
        if not self._failed_once:
            self._failed_once = True
            raise RuntimeError("transient tick failure")
        return await super().run_tick(tick_id=tick_id, max_pairs=max_pairs)


class BlockedLeaseRepo(FakeLeaseRepo):
    async def try_claim(self, session, engine: str, tick_id: int) -> bool:
        return False

    async def is_done(self, session, engine: str, tick_id: int) -> bool:
        return False


@pytest.mark.asyncio
async def test_scheduler_triggers_handlers_on_intervals() -> None:
    clock = GameClock(mode="game_driven")
    gossip = FakeHandler()
    event = FakeHandler()
    scheduler = TickScheduler(clock=clock, gossip_handler=gossip, event_handler=event, gossip_interval=2, event_interval=3)

    fake_session = cast(Any, FakeSession())

    await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)
    assert gossip.calls == []
    assert event.calls == []

    await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)
    assert gossip.calls == [2]
    assert event.calls == []

    await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)
    assert event.calls == [3]


@pytest.mark.asyncio
async def test_scheduler_processes_crossed_intervals_when_jump_advancing() -> None:
    clock = GameClock(mode="game_driven")
    gossip = FakeHandler()
    event = FakeHandler()
    scheduler = TickScheduler(clock=clock, gossip_handler=gossip, event_handler=event, gossip_interval=2, event_interval=3)

    fake_session = cast(Any, FakeSession())
    await scheduler.advance(session=fake_session, tick_delta=6, time_delta_seconds=6)

    assert gossip.calls == [2, 4, 6]
    assert event.calls == [3, 6]


@pytest.mark.asyncio
async def test_throwing_event_does_not_stop_loop_and_clock_advances() -> None:
    # S1.3: a throwing engine must not kill the loop; clock advances normally.
    clock = GameClock(mode="game_driven")
    gossip = FakeHandler()
    event = FailingHandler(fail_on_tick=3)
    scheduler = TickScheduler(clock=clock, gossip_handler=gossip, event_handler=event, gossip_interval=2, event_interval=3)

    fake_session = cast(Any, FakeSession())

    # First advance: event throws on tick 3, but loop must not raise.
    result = await scheduler.advance(session=fake_session, tick_delta=3, time_delta_seconds=3)

    # Gossip ran on tick 2 (interval=2). Event failed but response entry is absent, not an error.
    assert gossip.calls == [2]
    assert event.calls == []
    # Clock advanced past the failing tick — tick 3 done, not retried.
    assert result["clock"]["tick_id"] == 3

    # Second advance covers ticks 4–6; FailingHandler._failed=True so event runs on tick 6.
    result2 = await scheduler.advance(session=fake_session, tick_delta=3, time_delta_seconds=3)
    assert gossip.calls == [2, 4, 6]
    assert event.calls == [6]
    assert result2["clock"]["tick_id"] == 6


@pytest.mark.asyncio
async def test_distributed_lease_allows_only_one_scheduler_to_run_tick() -> None:
    shared_lease = FakeLeaseRepo()
    gossip_a = FakeHandler()
    event_a = FakeHandler()
    gossip_b = FakeHandler()
    event_b = FakeHandler()

    scheduler_a = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=gossip_a,
        event_handler=event_a,
        gossip_interval=2,
        event_interval=2,
        distributed_lease_enabled=True,
        lease_repo=shared_lease,
    )
    scheduler_b = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=gossip_b,
        event_handler=event_b,
        gossip_interval=2,
        event_interval=2,
        distributed_lease_enabled=True,
        lease_repo=shared_lease,
    )

    fake_session = cast(Any, FakeSession())
    await scheduler_a.advance(session=fake_session, tick_delta=2, time_delta_seconds=2)
    await scheduler_b.advance(session=fake_session, tick_delta=2, time_delta_seconds=2)

    assert gossip_a.calls == [2]
    assert event_a.calls == [2]
    assert gossip_b.calls == []
    assert event_b.calls == []


@pytest.mark.asyncio
async def test_distributed_lease_engine_failure_is_isolated_and_lease_marked_failed() -> None:
    # S1.3: distributed lease engine failure is caught; loop continues; lease marked failed.
    shared_lease = FakeLeaseRepo()
    gossip = FirstTickFailingHandler()
    event = FakeHandler()
    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=gossip,
        event_handler=event,
        gossip_interval=1,
        event_interval=99,
        distributed_lease_enabled=True,
        lease_repo=shared_lease,
    )

    fake_session = cast(Any, FakeSession())
    # Must not raise — engine failure is isolated.
    result = await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)

    # Lease was marked failed and gossip did not produce a result.
    assert shared_lease.failed == [("gossip", 1)]
    assert gossip.calls == []
    # Clock still advanced past the failing tick.
    assert result["clock"]["tick_id"] == 1

    # Second advance processes tick 2; gossip succeeds (FirstTickFailingHandler one-shot).
    await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)
    assert gossip.calls == [2]


@pytest.mark.asyncio
async def test_distributed_unresolved_tick_does_not_advance_clock() -> None:
    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=FakeHandler(),
        event_handler=FakeHandler(),
        gossip_interval=1,
        event_interval=99,
        distributed_lease_enabled=True,
        lease_repo=BlockedLeaseRepo(),
    )

    fake_session = cast(Any, FakeSession())
    response = await scheduler.advance(session=fake_session, tick_delta=1, time_delta_seconds=1)

    assert response["clock"]["tick_id"] == 0
