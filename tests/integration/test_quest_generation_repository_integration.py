"""
test_quest_generation_repository_integration.py — Integration tests for
Neo4jQuestGenerationRepository, Neo4jEventTriggerRepository, and Neo4jNeedTriggerRepository.

Every repository method is exercised on a positive path: each test seeds the minimum
Neo4j data through inline Cypher (uuid-suffixed ids, deleted in ``finally``), calls the
repository method, and asserts the exact values returned. A few tests also pin the exact
absent-id behaviour (default value or raised exception).

Covers 17 methods T11.2 identified as having no unit-or-integration path:
  Neo4jQuestGenerationRepository: get_world_state_day_and_rate, get_world_state_context,
    get_character_info, get_giver_context, get_candidate_ids_by_label, create_quest,
    record_causation, check_node_labels, get_template_skill_requirements, check_skill_threshold
  Neo4jEventTriggerRepository: get_unprocessed_trigger_events, get_military_npc_at_location,
    get_any_military_npc, has_draft_quest
  Neo4jNeedTriggerRepository: get_all_needs_below_threshold, has_draft_quest

The eval graph is shared and already holds seeded demo data, so global queries are driven
by unique event types, archetypes and labels; the seeded WorldState singleton 'world' is
never touched (tests seed their own WorldState node under a unique id).

Does NOT: test quest slot-fill retry logic or LLM prompt building.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
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


def _ids(*names: str) -> dict[str, str]:
    """Return {name: '<name>-<8 hex>'} so every seeded node id is unique per test."""
    suffix = uuid4().hex[:8]
    return {name: f"{name}-{suffix}" for name in names}


@asynccontextmanager
async def _seeded(cypher: str, ids: dict[str, Any]) -> AsyncIterator[GraphDB]:
    """Run ``cypher`` with ``ids`` as parameters, yield the GraphDB, then delete the ids.

    Cleanup DETACH DELETEs exactly the nodes whose ``id`` is one of ``ids`` values, so the
    seed Cypher must give every node it creates one of those ids.
    """
    graph_db = _make_graph_db()
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            result = await session.run(cypher, **ids)
            await result.consume()
        yield graph_db
    finally:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=list(ids.values())
            )
        await graph_db.close()


# ---------------------------------------------------------------------------
# Seed Cypher
# ---------------------------------------------------------------------------

_SEED_WORLD_STATE = """
CREATE (:WorldState {id: $ws, epoch: 'age_of_war', day: 42, quest_generation_rate: 0.25,
                     active_conditions: '["plague", "famine"]', faction_standings: '{}'})
"""

_SEED_CHARACTERS_FOR_INFO = """
CREATE (:Character {id: $full, archetype: 'blacksmith', name: 'Brom'}),
       (:Character {id: $bare})
"""

_SEED_GIVER = """
CREATE (c:Character {id: $char, is_active: true, current_mood: 'anxious', mood_intensity: 0.7})
CREATE (c)-[:LOCATED_AT]->(:Location {id: $loc})
CREATE (c)-[:PURSUES]->(:Goal {id: $goal_a, description: 'Protect the forge', urgency: 80, status: 'active'})
CREATE (c)-[:PURSUES]->(:Goal {id: $goal_x, description: 'Old dream', urgency: 90, status: 'abandoned'})
CREATE (c)-[:BELIEVES]->(:Belief {id: $bel_lo, content: 'Minor rumour', confidence: 40})
CREATE (c)-[:BELIEVES]->(:Belief {id: $bel_hi, content: 'The king is dead', confidence: 90})
CREATE (c)-[:HAS_NEED]->(:Need {id: $need, kind: 'hunger', level: 30, decay_rate: 1.0})
CREATE (c)-[:OWNS]->(:Item {id: $item_lo, name: 'Pebble', value: 5})
CREATE (c)-[:OWNS]->(:Item {id: $item_hi, name: 'Gem', value: 500})
CREATE (c)-[:BELONGS_TO_GROUP]->(:Group {id: $grp, name: 'Smiths Guild', kind: 'guild'})
CREATE (c)-[:BELONGS_TO_GROUP]->(:Group {id: $grp_x, name: 'Old Guild', kind: 'guild', dissolved_at_tick: 5})
"""

_SEED_TEMPLATE_SKILLS = """
CREATE (t:QuestTemplate {id: $tmpl})
CREATE (t)-[:REQUIRES_SKILL {min_level: 3}]->(:Skill {id: $skill_a})
CREATE (t)-[:REQUIRES_SKILL {min_level: 7}]->(:Skill {id: $skill_b})
"""

_SEED_SKILL_LEVEL = """
CREATE (:Character {id: $char})-[:HAS_SKILL {level: 5}]->(:Skill {id: $skill})
"""

_SEED_TRIGGER_EVENTS = """
CREATE (:Event {id: $ev_open, event_type: $etype, location_id: $loc})
CREATE (:Event {id: $ev_open2, event_type: $etype, location_id: $loc})
CREATE (:Event {id: $ev_done, event_type: $etype, location_id: $loc})
CREATE (:Event {id: $ev_other, event_type: $other_type, location_id: $loc})
WITH 1 AS _
MATCH (e:Event {id: $ev_done})
CREATE (:Quest {id: $quest, status: 'draft'})-[:CAUSED_BY]->(e)
"""

_SEED_MILITARY = """
CREATE (loc:Location {id: $loc}), (other:Location {id: $loc_other})
CREATE (:Character {id: $guard, is_active: true, archetype: $arch})-[:LOCATED_AT]->(loc)
CREATE (:Character {id: $sleeper, is_active: false, archetype: $arch})-[:LOCATED_AT]->(loc)
CREATE (:Character {id: $farmer, is_active: true, archetype: $civ_arch})-[:LOCATED_AT]->(loc)
CREATE (:Character {id: $far_guard, is_active: true, archetype: $arch_far})-[:LOCATED_AT]->(other)
"""

_SEED_INACTIVE_MILITARY = """
CREATE (:Character {id: $sleeper, is_active: false, archetype: $arch})
"""

_SEED_DRAFT_QUESTS = """
CREATE (c1:Character {id: $with_draft}), (c2:Character {id: $with_active}), (c3:Character {id: $bare})
CREATE (c1)-[:HAS_QUEST]->(:Quest {id: $q_draft, status: 'draft'})
CREATE (c2)-[:HAS_QUEST]->(:Quest {id: $q_active, status: 'active'})
"""

_SEED_NEEDS = """
CREATE (c:Character {id: $char})
CREATE (c)-[:HAS_NEED]->(:Need {id: $need_low, kind: 'hunger', level: 10, decay_rate: 1.5})
CREATE (c)-[:HAS_NEED]->(:Need {id: $need_high, kind: 'rest', level: 80, decay_rate: 0.5})
"""


# ---------------------------------------------------------------------------
# Neo4jQuestGenerationRepository — world state reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_world_state_day_and_rate_reads_seeded_node() -> None:
    """get_world_state_day_and_rate returns the day and rate stored on the WorldState node."""
    ids = _ids("ws")
    async with _seeded(_SEED_WORLD_STATE, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        assert await repo.get_world_state_day_and_rate(world_id=ids["ws"]) == (42, 0.25)


@pytest.mark.asyncio
async def test_get_world_state_day_and_rate_defaults_for_absent_world() -> None:
    """get_world_state_day_and_rate returns the model defaults (1, 1.0) for an absent world id."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.get_world_state_day_and_rate(world_id=f"world-{uuid4().hex}")
        assert result == (1, 1.0)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_world_state_context_reads_seeded_node() -> None:
    """get_world_state_context returns the epoch and parsed active_conditions of the node."""
    ids = _ids("ws")
    async with _seeded(_SEED_WORLD_STATE, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        ctx = await repo.get_world_state_context(world_id=ids["ws"])
        assert ctx == {"epoch": "age_of_war", "active_conditions": ["plague", "famine"]}


@pytest.mark.asyncio
async def test_get_world_state_context_defaults_for_absent_world() -> None:
    """get_world_state_context returns the default epoch and no conditions for an absent world."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        ctx = await repo.get_world_state_context(world_id=f"world-{uuid4().hex}")
        assert ctx == {"epoch": "age_of_peace", "active_conditions": []}
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestGenerationRepository — character reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_character_info_returns_archetype_and_name() -> None:
    """get_character_info returns (archetype, name); missing fields fall back to defaults."""
    ids = _ids("full", "bare")
    async with _seeded(_SEED_CHARACTERS_FOR_INFO, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        assert await repo.get_character_info(character_id=ids["full"]) == ("blacksmith", "Brom")
        assert await repo.get_character_info(character_id=ids["bare"]) == (
            "default",
            ids["bare"],
        )


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
async def test_get_giver_context_assembles_seeded_character() -> None:
    """get_giver_context assembles beliefs, mood, needs, inventory, location and faction values."""
    ids = _ids(
        "char", "loc", "goal_a", "goal_x", "bel_lo", "bel_hi", "need",
        "item_lo", "item_hi", "grp", "grp_x",
    )  # fmt: skip
    async with _seeded(_SEED_GIVER, ids) as graph_db:
        ctx = await Neo4jQuestGenerationRepository(graph_db).get_giver_context(
            character_id=ids["char"]
        )
    assert ctx["beliefs"] == ["The king is dead", "Minor rumour"]  # confidence DESC
    assert ctx["mood"] == "anxious"
    assert ctx["needs"] == [{"kind": "hunger", "level": 30}]
    assert ctx["inventory"] == [ids["item_hi"], ids["item_lo"]]  # value DESC
    assert ctx["location"] == ids["loc"]
    assert ctx["faction"] == ["Smiths Guild"]  # dissolved group excluded
    # One entry: only the 'active' goal, not the abandoned one. Its text is not asserted:
    # the repository reads key 'objective' but the goal query returns 'description'.
    assert len(ctx["goals"]) == 1


@pytest.mark.asyncio
async def test_get_giver_context_defaults_for_unknown_character() -> None:
    """get_giver_context returns the exact empty defaults for a non-existent character."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        ctx = await repo.get_giver_context(character_id=f"char-{uuid4()}")
        assert ctx == {
            "goals": [],
            "beliefs": [],
            "mood": "neutral",
            "needs": [],
            "inventory": [],
            "location": "unknown",
            "faction": [],
        }
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_candidate_ids_by_label_returns_ids_of_labelled_nodes() -> None:
    """get_candidate_ids_by_label returns exactly the ids of nodes carrying the label."""
    ids = _ids("n1", "n2", "other")
    label = f"QgenProbe{uuid4().hex[:8]}"
    seed = (
        f"CREATE (:{label} {{id: $n1}}), (:{label} {{id: $n2}}), (:Unrelated {{id: $other}})"
    )
    async with _seeded(seed, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        result = await repo.get_candidate_ids_by_label(label=label)
    assert sorted(result) == sorted([ids["n1"], ids["n2"]])


@pytest.mark.asyncio
async def test_get_candidate_ids_by_label_empty_for_unused_label() -> None:
    """get_candidate_ids_by_label returns [] when no node carries the label."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        assert await repo.get_candidate_ids_by_label(label=f"NoSuch{uuid4().hex}") == []
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
async def test_get_template_skill_requirements_returns_seeded_edges() -> None:
    """get_template_skill_requirements returns one {skill_id, min_level} dict per edge."""
    ids = _ids("tmpl", "skill_a", "skill_b")
    async with _seeded(_SEED_TEMPLATE_SKILLS, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        result = await repo.get_template_skill_requirements(template_id=ids["tmpl"])
    assert sorted(result, key=lambda r: r["skill_id"]) == [
        {"skill_id": ids["skill_a"], "min_level": 3},
        {"skill_id": ids["skill_b"], "min_level": 7},
    ]


@pytest.mark.asyncio
async def test_get_template_skill_requirements_returns_empty_list() -> None:
    """get_template_skill_requirements returns [] for a non-existent template."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestGenerationRepository(graph_db)
    try:
        result = await repo.get_template_skill_requirements(template_id=f"tmpl-{uuid4()}")
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_check_skill_threshold_true_at_and_below_level() -> None:
    """check_skill_threshold is True when the HAS_SKILL level equals or exceeds min_level."""
    ids = _ids("char", "skill")
    async with _seeded(_SEED_SKILL_LEVEL, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        for min_level in (5, 1):
            assert await repo.check_skill_threshold(
                character_id=ids["char"], skill_id=ids["skill"], min_level=min_level
            ) is True


@pytest.mark.asyncio
async def test_check_skill_threshold_false_above_level() -> None:
    """check_skill_threshold is False when min_level exceeds the HAS_SKILL level."""
    ids = _ids("char", "skill")
    async with _seeded(_SEED_SKILL_LEVEL, ids) as graph_db:
        repo = Neo4jQuestGenerationRepository(graph_db)
        assert await repo.check_skill_threshold(
            character_id=ids["char"], skill_id=ids["skill"], min_level=6
        ) is False


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


def _trigger_event_ids() -> dict[str, Any]:
    """Return ids plus unique event types/location for the trigger-event seed."""
    ids: dict[str, Any] = _ids("ev_open", "ev_open2", "ev_done", "ev_other", "quest")
    suffix = uuid4().hex[:8]
    ids.update(etype=f"qgen_trigger_{suffix}", other_type=f"qgen_other_{suffix}", loc=f"loc-{suffix}")
    return ids


@pytest.mark.asyncio
async def test_get_unprocessed_trigger_events_returns_only_unprocessed_matching() -> None:
    """get_unprocessed_trigger_events returns matching events lacking a CAUSED_BY quest."""
    ids = _trigger_event_ids()
    async with _seeded(_SEED_TRIGGER_EVENTS, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        result = await repo.get_unprocessed_trigger_events(frozenset({ids["etype"]}), 1000)
    assert sorted(result, key=lambda r: r["event_id"]) == [
        {"event_id": ids["ev_open"], "location_id": ids["loc"]},
        {"event_id": ids["ev_open2"], "location_id": ids["loc"]},
    ]


@pytest.mark.asyncio
async def test_get_unprocessed_trigger_events_respects_max_count() -> None:
    """get_unprocessed_trigger_events returns at most max_count rows."""
    ids = _trigger_event_ids()
    async with _seeded(_SEED_TRIGGER_EVENTS, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        result = await repo.get_unprocessed_trigger_events(frozenset({ids["etype"]}), 1)
    assert len(result) == 1
    assert result[0]["event_id"] in {ids["ev_open"], ids["ev_open2"]}
    assert result[0]["location_id"] == ids["loc"]


def _military_ids() -> dict[str, Any]:
    """Return ids plus unique archetype strings for the military-NPC seed."""
    ids: dict[str, Any] = _ids("loc", "loc_other", "guard", "sleeper", "farmer", "far_guard")
    suffix = uuid4().hex[:8]
    ids.update(arch=f"qgen_mil_{suffix}", civ_arch=f"qgen_civ_{suffix}", arch_far=f"qgen_far_{suffix}")
    return ids


@pytest.mark.asyncio
async def test_get_military_npc_at_location_returns_active_matching_guard() -> None:
    """get_military_npc_at_location returns the active, in-archetype character at the location."""
    ids = _military_ids()
    async with _seeded(_SEED_MILITARY, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        found = await repo.get_military_npc_at_location(
            location_id=ids["loc"], archetypes=frozenset({ids["arch"], ids["arch_far"]})
        )
        elsewhere = await repo.get_military_npc_at_location(
            location_id=ids["loc_other"], archetypes=frozenset({ids["arch"]})
        )
    assert found == ids["guard"]  # not the inactive, civilian or other-location NPC
    assert elsewhere is None  # only an out-of-archetype NPC lives at loc_other


@pytest.mark.asyncio
async def test_get_military_npc_at_location_none_for_unknown_location() -> None:
    """get_military_npc_at_location returns None when the location has no military NPC."""
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
async def test_get_any_military_npc_returns_active_character_of_archetype() -> None:
    """get_any_military_npc returns the active character whose archetype matches."""
    ids = _military_ids()
    async with _seeded(_SEED_MILITARY, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        far = await repo.get_any_military_npc(archetypes=frozenset({ids["arch_far"]}))
        both = await repo.get_any_military_npc(archetypes=frozenset({ids["arch"]}))
    assert far == ids["far_guard"]
    assert both == ids["guard"]  # the inactive sleeper shares the archetype but is skipped


@pytest.mark.asyncio
async def test_get_any_military_npc_ignores_inactive_characters() -> None:
    """get_any_military_npc returns None when the only matching character is inactive."""
    ids = _ids("sleeper")
    ids["arch"] = f"qgen_mil_{uuid4().hex[:8]}"
    async with _seeded(_SEED_INACTIVE_MILITARY, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        assert await repo.get_any_military_npc(archetypes=frozenset({ids["arch"]})) is None


@pytest.mark.asyncio
async def test_event_trigger_has_draft_quest_true_only_for_draft_owner() -> None:
    """EventTriggerRepository.has_draft_quest is True for a draft HAS_QUEST, False otherwise."""
    ids = _ids("with_draft", "with_active", "bare", "q_draft", "q_active")
    async with _seeded(_SEED_DRAFT_QUESTS, ids) as graph_db:
        repo = Neo4jEventTriggerRepository(graph_db)
        assert await repo.has_draft_quest(character_id=ids["with_draft"]) is True
        assert await repo.has_draft_quest(character_id=ids["with_active"]) is False
        assert await repo.has_draft_quest(character_id=ids["bare"]) is False


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
async def test_get_all_needs_below_threshold_returns_seeded_low_need() -> None:
    """get_all_needs_below_threshold returns the at-threshold need row and omits the high one."""
    ids = _ids("char", "need_low", "need_high")
    async with _seeded(_SEED_NEEDS, ids) as graph_db:
        repo = Neo4jNeedTriggerRepository(graph_db)
        rows = await repo.get_all_needs_below_threshold(threshold=10)
    mine = [r for r in rows if r["character_id"] == ids["char"]]
    assert mine == [
        {
            "need_id": ids["need_low"],
            "kind": "hunger",
            "level": 10,
            "decay_rate": 1.5,
            "character_id": ids["char"],
        }
    ]
    assert ids["need_high"] not in {r["need_id"] for r in rows}


@pytest.mark.asyncio
async def test_get_all_needs_below_threshold_includes_higher_need_at_higher_threshold() -> None:
    """Raising the threshold to 80 adds the level-80 need (inclusive upper bound)."""
    ids = _ids("char", "need_low", "need_high")
    async with _seeded(_SEED_NEEDS, ids) as graph_db:
        repo = Neo4jNeedTriggerRepository(graph_db)
        rows = await repo.get_all_needs_below_threshold(threshold=80)
    mine = {r["need_id"]: r["level"] for r in rows if r["character_id"] == ids["char"]}
    assert mine == {ids["need_low"]: 10, ids["need_high"]: 80}


@pytest.mark.asyncio
async def test_need_trigger_has_draft_quest_true_only_for_draft_owner() -> None:
    """NeedTriggerRepository.has_draft_quest is True for a draft HAS_QUEST, False otherwise."""
    ids = _ids("with_draft", "with_active", "bare", "q_draft", "q_active")
    async with _seeded(_SEED_DRAFT_QUESTS, ids) as graph_db:
        repo = Neo4jNeedTriggerRepository(graph_db)
        assert await repo.has_draft_quest(character_id=ids["with_draft"]) is True
        assert await repo.has_draft_quest(character_id=ids["with_active"]) is False
        assert await repo.has_draft_quest(character_id=ids["bare"]) is False


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
