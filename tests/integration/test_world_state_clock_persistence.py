"""
test_world_state_clock_persistence.py - Integration tests for the persisted game clock (ISSUE-165).

Exercises what unit mocks cannot: the monotonic CASE guard in real Cypher, the narrow
persist_clock_state writer, and clock survival across a simulated process restart.

Does NOT: test engines, dialogue, or the HTTP layer.

Dependencies injected: Neo4j test environment via env vars (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.graph.world_state.world_state_writer import (
    persist_clock_state,
    upsert_world_state,
)
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.world.world_state import WorldState


def _neo4j_creds() -> tuple[str, str, str]:
    """Return (uri, user, password) or skip the test."""
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


@pytest.fixture
async def session():
    """Yield a Neo4j session and drop the test world node afterwards."""
    uri, user, password = _neo4j_creds()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    world_id = f"world_test_{uuid4().hex[:8]}"
    async with driver.session() as neo_session:
        neo_session.world_id = world_id  # type: ignore[attr-defined]
        try:
            yield neo_session
        finally:
            await neo_session.run("MATCH (w:WorldState {id: $id}) DETACH DELETE w", id=world_id)
    await driver.close()


@pytest.mark.asyncio
async def test_world_state_tick_round_trips(session):
    """tick_id and game_time_seconds survive a write/read cycle through Neo4j."""
    world_id = session.world_id
    await upsert_world_state(session, WorldState(id=world_id, tick_id=17, game_time_seconds=340))

    stored = await get_world_state(session, world_id=world_id)
    assert stored.tick_id == 17
    assert stored.game_time_seconds == 340


@pytest.mark.asyncio
async def test_merge_never_lowers_tick(session):
    """A stale WorldState snapshot written back must not regress the persisted tick.

    This is the guard for story_pacing_engine / event_emission_service, which read a
    WorldState, model_copy it, and write it back — possibly straddling a tick advance.
    """
    world_id = session.world_id
    await upsert_world_state(session, WorldState(id=world_id, tick_id=17, game_time_seconds=340))
    await upsert_world_state(session, WorldState(id=world_id, tick_id=3, game_time_seconds=30))

    stored = await get_world_state(session, world_id=world_id)
    assert stored.tick_id == 17
    assert stored.game_time_seconds == 340


@pytest.mark.asyncio
async def test_persist_clock_state_does_not_touch_other_fields(session):
    """The narrow writer must leave engine-owned world fields alone."""
    world_id = session.world_id
    await upsert_world_state(
        session,
        WorldState(id=world_id, epoch="age_of_war", weather="storm", tick_id=1, game_time_seconds=10),
    )

    await persist_clock_state(session, world_id=world_id, tick_id=99, game_time_seconds=990)

    stored = await get_world_state(session, world_id=world_id)
    assert stored.tick_id == 99
    assert stored.game_time_seconds == 990
    assert stored.epoch == "age_of_war"
    assert stored.weather == "storm"


@pytest.mark.asyncio
async def test_persist_clock_state_is_monotonic(session):
    """persist_clock_state carries the same never-rewind guarantee as the full MERGE."""
    world_id = session.world_id
    await persist_clock_state(session, world_id=world_id, tick_id=50, game_time_seconds=500)
    await persist_clock_state(session, world_id=world_id, tick_id=8, game_time_seconds=80)

    stored = await get_world_state(session, world_id=world_id)
    assert stored.tick_id == 50
    assert stored.game_time_seconds == 500


@pytest.mark.asyncio
async def test_restart_resumes_from_persisted_tick(session):
    """A fresh GameClock hydrated from the graph continues, rather than replaying from 0."""
    world_id = session.world_id
    await persist_clock_state(session, world_id=world_id, tick_id=3, game_time_seconds=30)

    restarted = GameClock(mode="game_driven")
    assert restarted.current_tick == 0

    persisted = await get_world_state(session, world_id=world_id)
    await restarted.restore(
        tick_id=persisted.tick_id,
        game_time_seconds=persisted.game_time_seconds,
    )
    state = await restarted.advance(tick_delta=1, time_delta_seconds=0)

    assert state.tick_id == 4
