"""
test_quest_generation_repository_integration.py — Integration tests for
Neo4jQuestGenerationRepository, Neo4jEventTriggerRepository, and Neo4jNeedTriggerRepository.

Covers 17 methods T11.2 identified as having no unit-or-integration path:
  Neo4jQuestGenerationRepository: get_world_state_day_and_rate, get_world_state_context,
    get_character_info, get_giver_context, get_candidate_ids_by_label, create_quest,
    record_causation, check_node_labels, get_template_skill_requirements, check_skill_threshold
  Neo4jEventTriggerRepository: get_unprocessed_trigger_events, get_military_npc_at_location,
    get_any_military_npc, has_draft_quest
  Neo4jNeedTriggerRepository: get_all_needs_below_threshold, has_draft_quest

Does NOT: test quest slot-fill retry logic or LLM prompt building.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.quest_generation_repository import (
    Neo4jEventTriggerRepository,
    Neo4jNeedTriggerRepository,
    Neo4jQuestGenerationRepository,
)


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


# ---------------------------------------------------------------------------
# Neo4jQuestGenerationRepository — world state reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_world_state_day_and_rate_returns_defaults() -> None:
    """get_world_state_day_and_rate returns (int, float) with defaults on empty graph."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        day, rate = await repo.get_world_state_day_and_rate()
        assert isinstance(day, int)
        assert isinstance(rate, float)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_world_state_context_returns_expected_keys() -> None:
    """get_world_state_context returns a dict with 'epoch' and 'active_conditions' keys."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        ctx = await repo.get_world_state_context()
        assert isinstance(ctx, dict)
        assert "epoch" in ctx
        assert "active_conditions" in ctx
        assert isinstance(ctx["active_conditions"], list)
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestGenerationRepository — character reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_info_raises_for_unknown_character() -> None:
    """get_character_info raises ValueError when the Character node does not exist."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        with pytest.raises(ValueError, match="not found in graph"):
            await repo.get_character_info(character_id=f"char-{uuid4()}")
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_giver_context_returns_expected_keys_for_unknown_character() -> None:
    """get_giver_context returns a dict with known keys even for a non-existent character."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        ctx = await repo.get_giver_context(character_id=f"char-{uuid4()}")
        assert isinstance(ctx, dict)
        for key in ("goals", "beliefs", "mood", "needs", "inventory", "location", "faction"):
            assert key in ctx
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_candidate_ids_by_label_returns_list() -> None:
    """get_candidate_ids_by_label returns a list (empty on clean graph)."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.get_candidate_ids_by_label(label="NonExistentLabel")
        assert isinstance(result, list)
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestGenerationRepository — graph writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_quest_writes_quest_node() -> None:
    """create_quest persists a Quest node readable back from the graph."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    quest_id = f"quest-gen-{uuid4().hex[:8]}"
    giver_id = f"char-{uuid4().hex[:8]}"
    payload = {
        "quest_id": quest_id,
        "description": "Integration test quest",
        "quest_giver_id": giver_id,
        "success_condition": "test",
        "status": "draft",
        "severity": 10,
        "created_at": "2026-01-01T00:00:00",
    }
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run("CREATE (c:Character {id: $id})", id=giver_id)

        await repo.create_quest(payload=payload)

        async with graph_db.get_session() as session:
            qr = await session.run(
                "MATCH (q:Quest {id: $id}) RETURN q.id AS id", id=quest_id
            )
            row = await qr.single()
        assert row is not None
        assert row["id"] == quest_id
    finally:
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN [$q, $c] DETACH DELETE n",
                q=quest_id,
                c=giver_id,
            )
        await graph_db.close()


@pytest.mark.asyncio
async def test_record_causation_writes_caused_by_edge() -> None:
    """record_causation writes a CAUSED_BY relationship between effect and cause nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    effect_id = f"effect-{uuid4().hex[:8]}"
    cause_id = f"cause-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "CREATE (e:Event {id: $eid}), (c:Event {id: $cid})",
                eid=effect_id,
                cid=cause_id,
            )

        await repo.record_causation(
            effect_node_id=effect_id,
            effect_node_type="Event",
            cause_event_id=cause_id,
            causation_strength=80,
            cause_type="direct",
            tick_lag=1,
        )

        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (e:Event {id: $eid})-[:CAUSED_BY]->(c:Event {id: $cid}) RETURN count(*) AS cnt",
                eid=effect_id,
                cid=cause_id,
            )
            row = await result.single()
        assert row is not None
        assert row["cnt"] == 1
    finally:
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN [$e, $c] DETACH DELETE n",
                e=effect_id,
                c=cause_id,
            )
        await graph_db.close()


@pytest.mark.asyncio
async def test_check_node_labels_returns_none_when_absent() -> None:
    """check_node_labels returns None for a node ID that does not exist."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.check_node_labels(node_id=f"node-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_check_node_labels_returns_labels_for_existing_node() -> None:
    """check_node_labels returns a list of labels when the node exists."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    node_id = f"char-label-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run("CREATE (c:Character {id: $id})", id=node_id)
        result = await repo.check_node_labels(node_id=node_id)
        assert result is not None
        assert "Character" in result
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=node_id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_template_skill_requirements_returns_empty_list() -> None:
    """get_template_skill_requirements returns [] for a non-existent template."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.get_template_skill_requirements(template_id=f"tmpl-{uuid4()}")
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_check_skill_threshold_returns_false_when_absent() -> None:
    """check_skill_threshold returns False when character or skill does not exist."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.check_skill_threshold(
            character_id=f"char-{uuid4()}",
            skill_id=f"skill-{uuid4()}",
            min_level=5,
        )
        assert result is False
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jEventTriggerRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unprocessed_trigger_events_returns_list() -> None:
    """get_unprocessed_trigger_events returns a list (empty on clean graph)."""
    graph_db = _make_graph_db()
    repo = Neo4jEventTriggerRepository(graph_db)
    try:
        result = await repo.get_unprocessed_trigger_events(
            frozenset({"combat", "trade"}), max_count=10
        )
        assert isinstance(result, list)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_military_npc_at_location_returns_none_on_empty_graph() -> None:
    """get_military_npc_at_location returns None when no military NPCs are present."""
    graph_db = _make_graph_db()
    repo = Neo4jEventTriggerRepository(graph_db)
    try:
        result = await repo.get_military_npc_at_location(
            location_id=f"loc-{uuid4()}",
            archetypes=frozenset({"soldier", "guard"}),
        )
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_any_military_npc_returns_none_on_empty_graph() -> None:
    """get_any_military_npc returns None when no military NPCs are present."""
    graph_db = _make_graph_db()
    repo = Neo4jEventTriggerRepository(graph_db)
    try:
        result = await repo.get_any_military_npc(archetypes=frozenset({"soldier"}))
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_event_trigger_has_draft_quest_returns_false_when_absent() -> None:
    """has_draft_quest in EventTriggerRepository returns False for a non-existent character."""
    graph_db = _make_graph_db()
    repo = Neo4jEventTriggerRepository(graph_db)
    try:
        result = await repo.has_draft_quest(character_id=f"char-{uuid4()}")
        assert result is False
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jNeedTriggerRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_needs_below_threshold_returns_list() -> None:
    """get_all_needs_below_threshold returns a list (empty on clean graph)."""
    graph_db = _make_graph_db()
    repo = Neo4jNeedTriggerRepository(graph_db)
    try:
        result = await repo.get_all_needs_below_threshold(threshold=50)
        assert isinstance(result, list)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_need_trigger_has_draft_quest_returns_false_when_absent() -> None:
    """has_draft_quest in NeedTriggerRepository returns False for a non-existent character."""
    graph_db = _make_graph_db()
    repo = Neo4jNeedTriggerRepository(graph_db)
    try:
        result = await repo.has_draft_quest(character_id=f"char-{uuid4()}")
        assert result is False
    finally:
        await graph_db.close()
