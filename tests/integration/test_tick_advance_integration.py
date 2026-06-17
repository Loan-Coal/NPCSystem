"""
test_tick_advance_integration.py - Integration tests for TickScheduler.advance against real Neo4j.

Exercises the stateful path that unit-test mocks cannot catch: SchedulerState writes,
tick-deduplication reads, and idempotency across simulated restarts.

Does NOT: test LLM engines, dialogue, auth, or gossip/event business logic.

Dependencies injected: Neo4j test environment via env vars (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler


def _neo4j_creds() -> tuple[str, str, str]:
    """Return (uri, user, password) or skip the test."""
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


class _FakeHandler:
    """Minimal engine stub — records tick_ids without any side effects."""

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def run_tick(self, *, tick_id: int, **_kwargs: Any) -> dict:
        """Record the tick_id and return a minimal result dict."""
        self.calls.append(tick_id)
        return {"tick_id": tick_id, "pairs": 0}


def _make_scheduler(
    scheduler_id: str,
    gossip: _FakeHandler,
    event: _FakeHandler,
    clock: GameClock | None = None,
) -> TickScheduler:
    return TickScheduler(
        clock=clock or GameClock(mode="manual"),
        gossip_handler=gossip,
        event_handler=event,
        gossip_interval=1,
        event_interval=1,
        scheduler_id=scheduler_id,
        distributed_lease_enabled=False,
    )


@pytest.mark.asyncio
async def test_tick_advance_writes_scheduler_state_to_neo4j() -> None:
    """Advancing one tick writes SchedulerState to Neo4j and invokes both handlers."""
    uri, user, password = _neo4j_creds()
    scheduler_id = f"test-advance-{uuid4()}"
    gossip = _FakeHandler()
    event = _FakeHandler()
    scheduler = _make_scheduler(scheduler_id, gossip, event)

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            result = await scheduler.advance(session, tick_delta=1, time_delta_seconds=10)

        assert result["clock"]["tick_id"] == 1
        assert len(result["gossip"]) == 1
        assert len(result["event"]) == 1
        assert gossip.calls == [1]
        assert event.calls == [1]

        # SchedulerState node must be persisted with tick 1 in gossip_ticks
        async with driver.session() as session:
            res = await session.run(
                "MATCH (s:SchedulerState {id: $id}) RETURN s.gossip_ticks AS gt",
                id=scheduler_id,
            )
            row = await res.single()

        assert row is not None, "SchedulerState node was not written to Neo4j"
        assert 1 in (row["gt"] or []), "tick 1 must be recorded in gossip_ticks"
    finally:
        async with driver.session() as session:
            await session.run(
                "MATCH (s:SchedulerState {id: $id}) DELETE s",
                id=scheduler_id,
            )
        await driver.close()


@pytest.mark.asyncio
async def test_tick_advance_idempotent_across_scheduler_restart() -> None:
    """Re-advancing the same tick on a fresh scheduler does not re-run handlers.

    Simulates a server restart: a new TickScheduler with the same scheduler_id but
    a fresh in-memory clock (starting at tick 0 again) must not re-execute gossip
    or event handlers for ticks already recorded in Neo4j.
    """
    uri, user, password = _neo4j_creds()
    scheduler_id = f"test-idempotent-{uuid4()}"

    gossip_1 = _FakeHandler()
    event_1 = _FakeHandler()

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        # First run: advance tick 1
        sched_1 = _make_scheduler(scheduler_id, gossip_1, event_1)
        async with driver.session() as session:
            await sched_1.advance(session, tick_delta=1, time_delta_seconds=10)
        assert gossip_1.calls == [1], "first advance must call gossip for tick 1"

        # Simulated restart: same scheduler_id, fresh clock at tick 0
        gossip_2 = _FakeHandler()
        event_2 = _FakeHandler()
        sched_2 = _make_scheduler(scheduler_id, gossip_2, event_2, clock=GameClock(mode="manual"))
        async with driver.session() as session:
            result = await sched_2.advance(session, tick_delta=1, time_delta_seconds=10)

        # Tick 1 is already done in Neo4j — neither handler should fire again
        assert gossip_2.calls == [], "gossip must not re-run for an already-completed tick"
        assert event_2.calls == [], "event must not re-run for an already-completed tick"
        assert result["gossip"] == [], "response gossip list must be empty (tick already done)"
    finally:
        async with driver.session() as session:
            await session.run(
                "MATCH (s:SchedulerState {id: $id}) DELETE s",
                id=scheduler_id,
            )
        await driver.close()
