"""
test_chapter_political_emotion_repository_integration.py — Integration tests for
Neo4jChapterRepository, Neo4jPoliticalRepository, Neo4jEmotionBootstrapRepository,
and Neo4jProactiveMemoryReadRepository.

Covers 7 methods T11.2 identified as having no unit-or-integration path. Each method has a
positive-path test that seeds the minimum graph through inline Cypher and asserts the exact
returned values (ids, ordering, filtering, field contents); absent-id tests assert exact
empty values (None / [] / 0) only. Global queries share the eval Neo4j with seeded demo data,
so those tests use unique ids and assert only on the rows they created:
  Neo4jChapterRepository: get_completed_quests_since_tick, get_max_beat_intensity_in_chapter
  Neo4jEmotionBootstrapRepository: get_emotion_fields
  Neo4jPoliticalRepository: get_agenda_votes, get_expired_open_agendas, set_agenda_status
  Neo4jProactiveMemoryReadRepository: get_unshared_memories

Does NOT: test engine labeling logic or LLM dialogue.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
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


def _uid(prefix: str) -> str:
    """Return a unique, cleanup-safe id with the given prefix."""
    return f"{prefix}-{uuid4().hex[:8]}"


@asynccontextmanager
async def _seeded(cypher: str, ids: list[str], **params: Any) -> AsyncIterator[GraphDB]:
    """Seed the graph with ``cypher``, yield the GraphDB, then DETACH DELETE nodes by ``ids``."""
    graph_db = _make_graph_db()
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(cypher, **params)
        yield graph_db
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=ids)
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jChapterRepository
# ---------------------------------------------------------------------------

_SEED_QUESTS = """
CREATE (:Quest {id: $q_new, title: 'Newest', status: 'completed', completed_at_tick: $t})
CREATE (:Quest {id: $q_mid, title: 'Middle', status: 'completed', completed_at_tick: $t - 10})
CREATE (:Quest {id: $q_old, title: 'Too old', status: 'completed',
                completed_at_tick: $t - 100})
CREATE (:Quest {id: $q_open, title: 'Not done', status: 'active', completed_at_tick: $t})
"""


@pytest.mark.asyncio
async def test_get_completed_quests_since_tick_filters_and_orders_seeded_quests() -> None:
    """get_completed_quests_since_tick returns completed quests at/after the tick, newest first."""
    tick = 900_000_000 + random.randint(0, 50_000_000)
    q_new, q_mid, q_old, q_open = (_uid("quest") for _ in range(4))
    async with _seeded(
        _SEED_QUESTS, [q_new, q_mid, q_old, q_open],
        q_new=q_new, q_mid=q_mid, q_old=q_old, q_open=q_open, t=tick,
    ) as db:
        rows = await Neo4jChapterRepository(db).get_completed_quests_since_tick(
            since_tick=tick - 50
        )
    mine = [row for row in rows if row["id"] in {q_new, q_mid, q_old, q_open}]
    assert mine == [
        {"id": q_new, "title": "Newest", "completed_at_tick": tick},
        {"id": q_mid, "title": "Middle", "completed_at_tick": tick - 10},
    ]


@pytest.mark.asyncio
async def test_get_max_beat_intensity_in_chapter_returns_zero_when_absent() -> None:
    """get_max_beat_intensity_in_chapter returns exactly 0 for a chapter with no beat nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jChapterRepository(graph_db)
    try:
        result = await repo.get_max_beat_intensity_in_chapter(chapter_id=_uid("chapter"))
        assert result == 0
    finally:
        await graph_db.close()


_SEED_BEATS = """
CREATE (:NarrativeBeat {id: $b1, chapter_id: $chapter, intensity: 30})
CREATE (:NarrativeBeat {id: $b2, chapter_id: $chapter, intensity: 75})
CREATE (:NarrativeBeat {id: $b3, chapter_id: $chapter, intensity: 50})
CREATE (:NarrativeBeat {id: $b4, chapter_id: $other_chapter, intensity: 99})
"""


@pytest.mark.asyncio
async def test_get_max_beat_intensity_in_chapter_returns_max_of_its_own_beats() -> None:
    """get_max_beat_intensity_in_chapter returns 75 (max of 30/75/50), ignoring another chapter."""
    chapter, other_chapter = _uid("chapter"), _uid("chapter")
    b1, b2, b3, b4 = (_uid("beat") for _ in range(4))
    async with _seeded(
        _SEED_BEATS, [b1, b2, b3, b4],
        b1=b1, b2=b2, b3=b3, b4=b4, chapter=chapter, other_chapter=other_chapter,
    ) as db:
        repo = Neo4jChapterRepository(db)
        assert await repo.get_max_beat_intensity_in_chapter(chapter_id=chapter) == 75
        assert await repo.get_max_beat_intensity_in_chapter(chapter_id=other_chapter) == 99


# ---------------------------------------------------------------------------
# Neo4jEmotionBootstrapRepository
# ---------------------------------------------------------------------------

_SEED_EMOTION = """
CREATE (:Character {id: $npc, emotion_valence: -0.5, emotion_arousal: 0.25,
                    emotion_mood_label: 'wary', emotion_updated_at_tick: 1234})
CREATE (:Character {id: $bare})
"""


@pytest.mark.asyncio
async def test_get_emotion_fields_returns_none_for_unknown_npc() -> None:
    """get_emotion_fields returns None when the character node does not exist."""
    graph_db = _make_graph_db()
    repo = Neo4jEmotionBootstrapRepository(graph_db)
    try:
        assert await repo.get_emotion_fields(_uid("npc")) is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_emotion_fields_returns_persisted_values_or_all_none() -> None:
    """get_emotion_fields returns the stored fields; a bare character yields four Nones."""
    npc, bare = _uid("npc"), _uid("npc")
    async with _seeded(_SEED_EMOTION, [npc, bare], npc=npc, bare=bare) as db:
        repo = Neo4jEmotionBootstrapRepository(db)
        stored = await repo.get_emotion_fields(npc)
        unset = await repo.get_emotion_fields(bare)
    assert stored == {
        "emotion_valence": -0.5,
        "emotion_arousal": 0.25,
        "emotion_mood_label": "wary",
        "emotion_updated_at_tick": 1234,
    }
    assert unset == {
        "emotion_valence": None,
        "emotion_arousal": None,
        "emotion_mood_label": None,
        "emotion_updated_at_tick": None,
    }


# ---------------------------------------------------------------------------
# Neo4jPoliticalRepository
# ---------------------------------------------------------------------------

_SEED_VOTES = """
CREATE (a:Agenda {id: $agenda, status: 'open', deadline_tick: 100})
CREATE (s1:Character {id: $s1, name: 'Supporter One'})
CREATE (s2:Character {id: $s2, name: 'Supporter Two'})
CREATE (o1:Character {id: $o1, name: 'Opposer One'})
CREATE (s1)-[:SUPPORTS_AGENDA {weight: 2}]->(a)
CREATE (s2)-[:SUPPORTS_AGENDA {weight: 5}]->(a)
CREATE (o1)-[:OPPOSES_AGENDA {weight: 3}]->(a)
"""


@pytest.mark.asyncio
async def test_get_agenda_votes_returns_empty_dicts_for_unknown_agenda() -> None:
    """get_agenda_votes returns exactly {'supports': [], 'opposes': []} for an unknown agenda."""
    graph_db = _make_graph_db()
    repo = Neo4jPoliticalRepository(graph_db)
    try:
        result = await repo.get_agenda_votes(agenda_id=_uid("agenda"))
        assert result == {"supports": [], "opposes": []}
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_agenda_votes_returns_supporters_and_opposers_with_weights() -> None:
    """get_agenda_votes splits SUPPORTS_AGENDA / OPPOSES_AGENDA voters with their weights."""
    agenda, s1, s2, o1 = _uid("agenda"), _uid("sup"), _uid("sup"), _uid("opp")
    async with _seeded(
        _SEED_VOTES, [agenda, s1, s2, o1], agenda=agenda, s1=s1, s2=s2, o1=o1
    ) as db:
        votes = await Neo4jPoliticalRepository(db).get_agenda_votes(agenda_id=agenda)
    supports = {row["character"]["id"]: row for row in votes["supports"]}
    assert set(votes) == {"supports", "opposes"}
    assert len(votes["supports"]) == 2
    assert supports[s1] == {"character": {"id": s1, "name": "Supporter One"}, "weight": 2}
    assert supports[s2] == {"character": {"id": s2, "name": "Supporter Two"}, "weight": 5}
    assert votes["opposes"] == [
        {"character": {"id": o1, "name": "Opposer One"}, "weight": 3}
    ]


_SEED_AGENDAS = """
CREATE (:Agenda {id: $a_past, status: 'open', deadline_tick: 100})
CREATE (:Agenda {id: $a_exact, status: 'open', deadline_tick: 200})
CREATE (:Agenda {id: $a_future, status: 'open', deadline_tick: 300})
CREATE (:Agenda {id: $a_closed, status: 'passed', deadline_tick: 100})
CREATE (:Agenda {id: $a_nodl, status: 'open'})
"""


@pytest.mark.asyncio
async def test_get_expired_open_agendas_returns_only_open_agendas_past_deadline() -> None:
    """get_expired_open_agendas includes open agendas with deadline <= tick (inclusive)."""
    a_past, a_exact, a_future, a_closed, a_nodl = (_uid("agenda") for _ in range(5))
    async with _seeded(
        _SEED_AGENDAS, [a_past, a_exact, a_future, a_closed, a_nodl],
        a_past=a_past, a_exact=a_exact, a_future=a_future, a_closed=a_closed, a_nodl=a_nodl,
    ) as db:
        rows = await Neo4jPoliticalRepository(db).get_expired_open_agendas(current_tick=200)
    by_id = {row["id"]: row for row in rows}
    seeded = {a_past, a_exact, a_future, a_closed, a_nodl}
    assert set(by_id) & seeded == {a_past, a_exact}
    assert by_id[a_past] == {"id": a_past, "status": "open", "deadline_tick": 100}
    assert by_id[a_exact] == {"id": a_exact, "status": "open", "deadline_tick": 200}


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


# ---------------------------------------------------------------------------
# Neo4jProactiveMemoryReadRepository
# ---------------------------------------------------------------------------

_SEED_MEMORIES = """
CREATE (c:Character {id: $npc})
CREATE (c)-[:REMEMBERS]->(:Memory {id: $m_low, content: 'a faded rumour', vividness: 20})
CREATE (c)-[:REMEMBERS]->(:Memory {id: $m_high, content: 'the fire', vividness: 90})
CREATE (c)-[:REMEMBERS]->(:Memory {id: $m_mid, content: 'the wedding', vividness: 55})
CREATE (:Character {id: $other})-[:REMEMBERS]->(:Memory {id: $m_other, content: 'not mine',
                                                         vividness: 100})
"""


@pytest.mark.asyncio
async def test_get_unshared_memories_returns_empty_for_unknown_npc() -> None:
    """get_unshared_memories returns exactly [] when the NPC has no memory nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jProactiveMemoryReadRepository(graph_db)
    try:
        assert await repo.get_unshared_memories(npc_id=_uid("npc"), k=10) == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unshared_memories_orders_by_vividness_and_honours_k() -> None:
    """get_unshared_memories returns the NPC's memories vividest-first, capped at k."""
    npc, other = _uid("npc"), _uid("npc")
    m_low, m_high, m_mid, m_other = (_uid("mem") for _ in range(4))
    async with _seeded(
        _SEED_MEMORIES, [npc, other, m_low, m_high, m_mid, m_other],
        npc=npc, other=other, m_low=m_low, m_high=m_high, m_mid=m_mid, m_other=m_other,
    ) as db:
        repo = Neo4jProactiveMemoryReadRepository(db)
        everything = await repo.get_unshared_memories(npc_id=npc, k=10)
        top_two = await repo.get_unshared_memories(npc_id=npc, k=2)
    assert everything == [
        {"memory_id": m_high, "content": "the fire", "vividness": 90, "shared": False},
        {"memory_id": m_mid, "content": "the wedding", "vividness": 55, "shared": False},
        {"memory_id": m_low, "content": "a faded rumour", "vividness": 20, "shared": False},
    ]
    assert [row["memory_id"] for row in top_two] == [m_high, m_mid]
