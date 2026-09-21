"""
test_chapter_political_emotion_repository_integration.py — Integration tests for
Neo4jChapterRepository, Neo4jPoliticalRepository, Neo4jEmotionBootstrapRepository,
and Neo4jProactiveMemoryReadRepository.

Covers 7 methods T11.2 identified as having no unit-or-integration path:
  Neo4jChapterRepository: get_completed_quests_since_tick, get_max_beat_intensity_in_chapter
  Neo4jEmotionBootstrapRepository: get_emotion_fields
  Neo4jPoliticalRepository: get_agenda_votes, get_expired_open_agendas, set_agenda_status
  Neo4jProactiveMemoryReadRepository: get_unshared_memories

Does NOT: test engine labeling logic or LLM dialogue.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.chapter_repository import Neo4jChapterRepository
from npc_engine.graph.repositories.political_repository import Neo4jPoliticalRepository
from npc_engine.graph.repositories.emotion_bootstrap_repository import Neo4jEmotionBootstrapRepository
from npc_engine.graph.repositories.proactive_memory_read_repository import Neo4jProactiveMemoryReadRepository


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
async def test_get_completed_quests_since_tick_returns_list() -> None:
    """get_completed_quests_since_tick returns a list (empty on a clean graph)."""
    graph_db = _make_graph_db()
    repo = Neo4jChapterRepository(graph_db)
    try:
        result = await repo.get_completed_quests_since_tick(since_tick=0)
        assert isinstance(result, list)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_max_beat_intensity_in_chapter_returns_zero_when_absent() -> None:
    """get_max_beat_intensity_in_chapter returns 0 for a chapter with no beat nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jChapterRepository(graph_db)
    try:
        result = await repo.get_max_beat_intensity_in_chapter(
            chapter_id=f"chapter-{uuid4()}"
        )
        assert result == 0
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_emotion_fields_returns_none_for_unknown_npc() -> None:
    """get_emotion_fields returns None when the character node does not exist."""
    graph_db = _make_graph_db()
    repo = Neo4jEmotionBootstrapRepository(graph_db)
    try:
        result = await repo.get_emotion_fields(f"npc-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_agenda_votes_returns_empty_dicts_for_unknown_agenda() -> None:
    """get_agenda_votes returns {'supports': [], 'opposes': []} for a non-existent agenda."""
    graph_db = _make_graph_db()
    repo = Neo4jPoliticalRepository(graph_db)
    try:
        result = await repo.get_agenda_votes(agenda_id=f"agenda-{uuid4()}")
        assert isinstance(result, dict)
        assert result.get("supports") == []
        assert result.get("opposes") == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_expired_open_agendas_returns_list() -> None:
    """get_expired_open_agendas returns a list (empty on a clean graph)."""
    graph_db = _make_graph_db()
    repo = Neo4jPoliticalRepository(graph_db)
    try:
        result = await repo.get_expired_open_agendas(current_tick=9999)
        assert isinstance(result, list)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_set_agenda_status_updates_agenda_node() -> None:
    """set_agenda_status changes the Agenda node's status field in real Cypher."""
    graph_db = _make_graph_db()
    repo = Neo4jPoliticalRepository(graph_db)
    agenda_id = f"agenda-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "CREATE (a:Agenda {id: $id, status: 'open', deadline_tick: 1})",
                id=agenda_id,
            )

        await repo.set_agenda_status(agenda_id=agenda_id, status="passed")

        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (a:Agenda {id: $id}) RETURN a.status AS status",
                id=agenda_id,
            )
            row = await result.single()
        assert row is not None
        assert row["status"] == "passed"
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (a:Agenda {id: $id}) DETACH DELETE a", id=agenda_id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unshared_memories_returns_empty_for_unknown_npc() -> None:
    """get_unshared_memories returns an empty list when the NPC has no memory nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jProactiveMemoryReadRepository(graph_db)
    try:
        result = await repo.get_unshared_memories(npc_id=f"npc-{uuid4()}", k=10)
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()
