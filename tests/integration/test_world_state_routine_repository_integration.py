"""
test_world_state_routine_repository_integration.py — Integration tests for
Neo4jWorldStateRepository and Neo4jRoutineRepository.

Covers 3 methods T11.2 identified as having no unit-or-integration path:
  Neo4jWorldStateRepository: get_world_state, upsert_world_state
  Neo4jRoutineRepository: clear_routine_override

Does NOT: test scheduler routing or engine logic.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository
from npc_engine.graph.repositories.routine_repository import Neo4jRoutineRepository
from npc_engine.world.world_state import WorldState


def _make_graph_db() -> GraphDB:
    """Build a GraphDB wired to the eval-stack Neo4j, or skip if env vars are absent."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    settings = Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        NEO4J_URI=uri,
        NEO4J_USER=user,
        NEO4J_PASSWORD=password,
    )
    return GraphDB(settings)


@pytest.mark.asyncio
async def test_get_world_state_returns_default_on_empty_graph() -> None:
    """get_world_state returns a WorldState with default tick_id when none has been written."""
    graph_db = _make_graph_db()
    repo = Neo4jWorldStateRepository(graph_db)
    try:
        state = await repo.get_world_state(world_id=f"world-test-{uuid4().hex[:8]}")
        assert isinstance(state, WorldState)
        assert state.tick_id == 0
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_upsert_world_state_round_trips_tick_id() -> None:
    """upsert_world_state writes and get_world_state reads back the correct tick_id."""
    graph_db = _make_graph_db()
    repo = Neo4jWorldStateRepository(graph_db)
    world_id = f"world-test-{uuid4().hex[:8]}"
    try:
        written = await repo.upsert_world_state(
            world_state=WorldState(id=world_id, tick_id=42, game_time_seconds=420)
        )
        assert written.tick_id == 42

        read_back = await repo.get_world_state(world_id=world_id)
        assert read_back.tick_id == 42
        assert read_back.game_time_seconds == 420
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (w:WorldState {id: $id}) DETACH DELETE w", id=world_id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_clear_routine_override_nulls_override_field() -> None:
    """clear_routine_override sets routine_override to null on the Character node."""
    graph_db = _make_graph_db()
    repo = Neo4jRoutineRepository(graph_db)
    char_id = f"char-test-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "CREATE (c:Character {id: $id, routine_override: 'some-override'})",
                id=char_id,
            )

        await repo.clear_routine_override(character_id=char_id)

        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (c:Character {id: $id}) RETURN c.routine_override AS override",
                id=char_id,
            )
            row = await result.single()
        assert row is not None
        assert row["override"] is None
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=char_id)
        await graph_db.close()
