"""
test_quest_repository_integration.py — Integration tests for Neo4jQuestLifecycleRepository,
Neo4jQuestOfferRepository, Neo4jQuestChainRepository, and Neo4jQuestRewardRepository.

Covers 15 public methods T11.2 identified as having no unit-or-integration path. The existing
test_quest_lifecycle_integration_v14 exercises the engine layer; this file exercises the
repository layer directly against real Cypher.

Read methods are tested on the positive path: each test seeds uniquely-id'd rows through inline
Cypher, calls the repository, and asserts the exact values returned (ids, statuses, counts, field
contents). The eval Neo4j is shared with seeded demo data, so tests assert only on their own rows
and delete exactly what they created in ``finally``.

Does NOT: test engine transition policies or HTTP routing.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.quest_repository import (
    Neo4jQuestChainRepository,
    Neo4jQuestLifecycleRepository,
    Neo4jQuestOfferRepository,
)
from npc_engine.graph.repositories.quest_reward_repository import Neo4jQuestRewardRepository


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


def _state(quest_id: str, player_id: str, status: str = "offered") -> dict[str, Any]:
    """Build a minimal quest state payload for repository tests."""
    return {
        "quest_id": quest_id,
        "player_id": player_id,
        "reward_source_id": "system",
        "title": "Integration test quest",
        "status": status,
        "objectives": [],
        "objective_progress": {},
        "item_rewards": [],
        "currency_reward": None,
        "rewards_applied": False,
    }


class _TestEvent(BaseModel):
    """Minimal Pydantic model satisfying _EventNode protocol for integration tests."""

    id: str
    producer: str = "test"
    origin_engine: str = "test"
    schema_version: str = "v1"
    provenance: dict[str, Any] = {}
    event_type: str = "test_event"
    summary: str = "test"
    severity: int = 10
    location_id: str = "test"
    occurred_at: str = "2026-01-01T00:00:00+00:00"
    tick_id: int = 1
    is_public: bool = True
    last_graph_updated_at: str = "2026-01-01T00:00:00+00:00"

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        """Return serializable dict with provenance dict (not JSON-encoded)."""
        return super().model_dump(mode=mode)


def _test_event(quest_id: str, player_id: str, request_suffix: str) -> _TestEvent:
    """Construct a valid test event node with complete provenance."""
    return _TestEvent(
        id=f"{quest_id}:{player_id}:test_event:{request_suffix}",
        provenance={
            "request_id": f"req-{request_suffix}",
            "idempotency_key": f"idem-{request_suffix}",
            "idempotency_request_hash": f"hash-{request_suffix}",
            "actor_id": "player-test",
            "reason": "integration test",
        },
    )


async def _exec(graph_db: GraphDB, cypher: str, **params: Any) -> None:
    """Run one write statement in its own session (connects the driver on first use)."""
    await graph_db.connect()
    async with graph_db.get_session() as session:
        result = await session.run(cypher, **params)
        await result.consume()


async def _delete_ids(graph_db: GraphDB, ids: list[str]) -> None:
    """DETACH DELETE every node whose id is in ``ids`` (ids are uuid-suffixed, test-owned)."""
    await _exec(graph_db, "MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=ids)


def _quest_props(quest_id: str, **overrides: Any) -> dict[str, Any]:
    """Return the full Quest-node property map that CYPHER_GET_QUEST projects."""
    props: dict[str, Any] = {
        "id": quest_id,
        "description": f"Recover the lost ledger ({quest_id})",
        "quest_giver_id": f"giver-{quest_id}",
        "target_id": f"target-{quest_id}",
        "reward_id": f"reward-{quest_id}",
        "success_condition": "ledger_returned",
        "failure_condition": "ledger_burned",
        "status": "offered",
        "severity": 7,
        "created_at": "2026-02-03T04:05:06+00:00",
        "completed_at": None,
        "source": "integration_test",
    }
    return {**props, **overrides}


async def _seed_quest(graph_db: GraphDB, props: dict[str, Any]) -> None:
    """Create one Quest node carrying ``props`` (null values are simply not stored)."""
    await _exec(graph_db, "CREATE (q:Quest) SET q = $props", props=props)


async def _seed_unlock(
    graph_db: GraphDB, src_id: str, dst_id: str, **edge_props: Any
) -> None:
    """Create an UNLOCKS edge between two existing Quest nodes with the given edge props."""
    await _exec(
        graph_db,
        "MATCH (a:Quest {id: $src}), (b:Quest {id: $dst}) "
        "CREATE (a)-[r:UNLOCKS]->(b) SET r = $props",
        src=src_id,
        dst=dst_id,
        props=edge_props,
    )


async def _seed_quest_state(
    graph_db: GraphDB, quest_id: str, player_id: str, *, status: str, **extra: Any
) -> None:
    """Create a raw QuestState node in the JSON-column shape the reader decodes."""
    props: dict[str, Any] = {
        "id": f"{quest_id}:{player_id}",
        "quest_id": quest_id,
        "player_id": player_id,
        "reward_source_id": "system",
        "title": f"State of {quest_id}",
        "status": status,
        "objectives_json": "[]",
        "objective_progress_json": "{}",
        "item_rewards_json": "[]",
        "rewards_applied": False,
        **extra,
    }
    await _exec(graph_db, "CREATE (s:QuestState) SET s = $props", props=props)


async def _seed_character(
    graph_db: GraphDB, character_id: str, balance: int | None
) -> None:
    """Create a Character node, with ``currency_balance`` only when ``balance`` is not None."""
    await _exec(
        graph_db,
        "CREATE (c:Character {id: $id, name: $id}) "
        "FOREACH (_ IN CASE WHEN $balance IS NULL THEN [] ELSE [1] END | "
        "SET c.currency_balance = $balance)",
        id=character_id,
        balance=balance,
    )


_RICH_STATE_COLUMNS: dict[str, Any] = {
    "reward_source_id": "npc-giver",
    "objectives_json": '[{"objective_id": "o1", "target_count": 2}]',
    "objective_progress_json": '{"o1": 1}',
    "item_rewards_json": '[{"item_id": "sword", "quantity": 3}]',
    "currency_reward_json": '{"amount": 40}',
    "rewards_applied": True,
}


# ---------------------------------------------------------------------------
# Neo4jQuestLifecycleRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_lifecycle_get_quest_state_returns_none_when_absent() -> None:
    """get_quest_state returns None for a quest that has never been persisted."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    try:
        result = await repo.get_quest_state(
            quest_id=f"q-{uuid4()}", player_id=f"p-{uuid4()}"
        )
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_get_quest_state_returns_seeded_state() -> None:
    """get_quest_state decodes the JSON columns of the matching QuestState, not another player's."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    other_player = f"p-{uuid4().hex[:8]}"
    try:
        await _seed_quest_state(
            graph_db,
            quest_id,
            player_id,
            status="accepted",
            **_RICH_STATE_COLUMNS,
        )
        await _seed_quest_state(graph_db, quest_id, other_player, status="failed")
        result = await repo.get_quest_state(quest_id=quest_id, player_id=player_id)
        assert result == {
            "quest_id": quest_id,
            "player_id": player_id,
            "reward_source_id": "npc-giver",
            "title": f"State of {quest_id}",
            "status": "accepted",
            "objectives": [{"objective_id": "o1", "target_count": 2}],
            "objective_progress": {"o1": 1},
            "item_rewards": [{"item_id": "sword", "quantity": 3}],
            "currency_reward": {"amount": 40},
            "rewards_applied": True,
        }
        other = await repo.get_quest_state(quest_id=quest_id, player_id=other_player)
        assert other is not None
        assert other["status"] == "failed"
        assert other["currency_reward"] is None
    finally:
        await _delete_ids(
            graph_db, [f"{quest_id}:{player_id}", f"{quest_id}:{other_player}"]
        )
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_get_world_state_hydrates_seeded_node() -> None:
    """get_world_state hydrates a seeded WorldState node, decoding its JSON-encoded fields."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    world_id = f"world-{uuid4().hex[:8]}"
    try:
        await _exec(
            graph_db,
            "CREATE (w:WorldState {id: $id, epoch: 'age_of_test', weather: 'storm', "
            "time_of_day: 'dusk', year: 12, season: 'autumn', day: 9, tick_id: 41, "
            "game_time_seconds: 7300, faction_standings: $standings, "
            "active_conditions: $conditions, last_updated_at: datetime()})",
            id=world_id,
            standings='{"guild": 15, "crown": -20}',
            conditions='["plague", "festival"]',
        )
        result = await repo.get_world_state(world_id=world_id)
        assert result.id == world_id
        assert result.epoch == "age_of_test"
        assert result.weather == "storm"
        assert result.time_of_day == "dusk"
        assert (result.year, result.season, result.day) == (12, "autumn", 9)
        assert (result.tick_id, result.game_time_seconds) == (41, 7300)
        assert result.faction_standings == {"guild": 15, "crown": -20}
        assert result.active_conditions == ["plague", "festival"]
    finally:
        await _delete_ids(graph_db, [world_id])
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_get_world_state_defaults_when_node_absent() -> None:
    """get_world_state returns the default model carrying the requested id when no node exists."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    world_id = f"world-{uuid4().hex[:8]}"
    try:
        result = await repo.get_world_state(world_id=world_id)
        assert result.id == world_id
        assert result.epoch == "age_of_peace"
        assert result.faction_standings == {}
        assert result.active_conditions == []
        assert (result.tick_id, result.game_time_seconds) == (0, 0)
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_emit_lifecycle_event_writes_event_node() -> None:
    """emit_lifecycle_event persists an Event node that can be read back."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    request_suffix = uuid4().hex[:8]
    event = _test_event(quest_id, player_id, request_suffix)
    try:
        await repo.emit_lifecycle_event(event_node=event)
        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (e:Event {id: $id}) RETURN e.id AS id", id=event.id
            )
            row = await result.single()
        assert row is not None
        assert row["id"] == event.id
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (e:Event {id: $id}) DETACH DELETE e", id=event.id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_persist_state_and_event() -> None:
    """persist_state_and_event writes QuestState + Event atomically."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    request_suffix = uuid4().hex[:8]
    event = _test_event(quest_id, player_id, request_suffix)
    try:
        stored = await repo.persist_state_and_event(
            quest_id=quest_id,
            player_id=player_id,
            state_payload=_state(quest_id, player_id, "accepted"),
            event_node=event,
        )
        assert stored["status"] == "accepted"
        assert stored["quest_id"] == quest_id
    finally:
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN [$qs, $ev] DETACH DELETE n",
                qs=f"{quest_id}:{player_id}",
                ev=event.id,
            )
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_lifecycle_update_quest_node_status() -> None:
    """update_quest_node_status changes the Quest node's status field."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "CREATE (q:Quest {id: $id, status: 'offered'})", id=quest_id
            )
        await repo.update_quest_node_status(quest_id=quest_id, status="completed")
        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (q:Quest {id: $id}) RETURN q.status AS status", id=quest_id
            )
            row = await result.single()
        assert row is not None
        assert row["status"] == "completed"
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (q:Quest {id: $id}) DETACH DELETE q", id=quest_id)
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestOfferRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_offer_get_quest_returns_none_when_absent() -> None:
    """get_quest returns None for a quest that has not been created."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestOfferRepository(graph_db)
    try:
        result = await repo.get_quest(quest_id=f"q-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_offer_get_quest_returns_seeded_quest() -> None:
    """get_quest returns every projected field of the requested Quest and only that Quest."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestOfferRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    other_id = f"q-{uuid4().hex[:8]}"
    props = _quest_props(quest_id, status="draft", severity=9)
    try:
        await _seed_quest(graph_db, props)
        await _seed_quest(graph_db, _quest_props(other_id, description="decoy"))
        result = await repo.get_quest(quest_id=quest_id)
        assert result == props
        assert result is not None
        assert result["completed_at"] is None
    finally:
        await _delete_ids(graph_db, [quest_id, other_id])
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_offer_update_quest_node_status() -> None:
    """update_quest_node_status in offer repo writes the new status to the Quest node."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestOfferRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(
                "CREATE (q:Quest {id: $id, status: 'draft'})", id=quest_id
            )
        await repo.update_quest_node_status(quest_id=quest_id, status="offered")
        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (q:Quest {id: $id}) RETURN q.status AS status", id=quest_id
            )
            row = await result.single()
        assert row is not None
        assert row["status"] == "offered"
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (q:Quest {id: $id}) DETACH DELETE q", id=quest_id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_offer_offer_quest_atomic_creates_offered_state() -> None:
    """offer_quest_atomic creates a QuestState with status='offered' atomically."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestOfferRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    request_suffix = uuid4().hex[:8]
    event = _test_event(quest_id, player_id, request_suffix)
    try:
        stored = await repo.offer_quest_atomic(
            quest_id=quest_id,
            player_id=player_id,
            state_payload=_state(quest_id, player_id, "offered"),
            event_node=event,
        )
        assert stored["status"] == "offered"
        assert stored["quest_id"] == quest_id
    finally:
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN [$qs, $ev] DETACH DELETE n",
                qs=f"{quest_id}:{player_id}",
                ev=event.id,
            )
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestChainRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_chain_get_quest_returns_none_when_absent() -> None:
    """get_quest in chain repo returns None for a non-existent quest."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    try:
        result = await repo.get_quest(quest_id=f"q-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_quest_returns_seeded_quest() -> None:
    """get_quest in chain repo returns the seeded Quest's projected fields, severity as int."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    props = _quest_props(
        quest_id, status="completed", completed_at="2026-03-04T05:06:07+00:00", severity=3
    )
    try:
        await _seed_quest(graph_db, props)
        result = await repo.get_quest(quest_id=quest_id)
        assert result == props
    finally:
        await _delete_ids(graph_db, [quest_id])
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_unlocked_quests_filters_by_outcome() -> None:
    """get_unlocked_quests returns only destinations of UNLOCKS edges matching the outcome."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    ids = {name: f"q-{name}-{uuid4().hex[:8]}" for name in ("src", "win1", "win2", "lose", "other")}
    try:
        for quest_id in ids.values():
            await _seed_quest(graph_db, _quest_props(quest_id))
        await _seed_unlock(graph_db, ids["src"], ids["win1"], on_outcome="completed")
        await _seed_unlock(graph_db, ids["src"], ids["win2"], on_outcome="completed")
        await _seed_unlock(graph_db, ids["src"], ids["lose"], on_outcome="failed")
        await _seed_unlock(graph_db, ids["other"], ids["lose"], on_outcome="completed")
        completed = await repo.get_unlocked_quests(quest_id=ids["src"], outcome="completed")
        failed = await repo.get_unlocked_quests(quest_id=ids["src"], outcome="failed")
        unmatched = await repo.get_unlocked_quests(quest_id=ids["src"], outcome="abandoned")
        assert sorted(completed) == sorted([ids["win1"], ids["win2"]])
        assert failed == [ids["lose"]]
        assert unmatched == []
    finally:
        await _delete_ids(graph_db, list(ids.values()))
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_unlocked_quests_absent_source_returns_empty() -> None:
    """get_unlocked_quests returns exactly [] for a source quest with no UNLOCKS edges."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    try:
        result = await repo.get_unlocked_quests(quest_id=f"q-{uuid4()}", outcome="completed")
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_choice_unlocked_quest_matches_choice_id() -> None:
    """get_choice_unlocked_quest returns the destination whose edge carries the choice id."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    ids = {name: f"q-{name}-{uuid4().hex[:8]}" for name in ("src", "a", "b", "plain")}
    choice_a, choice_b = f"choice-a-{uuid4().hex[:8]}", f"choice-b-{uuid4().hex[:8]}"
    try:
        for quest_id in ids.values():
            await _seed_quest(graph_db, _quest_props(quest_id))
        await _seed_unlock(graph_db, ids["src"], ids["a"], on_choice_id=choice_a)
        await _seed_unlock(graph_db, ids["src"], ids["b"], on_choice_id=choice_b)
        await _seed_unlock(graph_db, ids["src"], ids["plain"], on_outcome="completed")
        assert await repo.get_choice_unlocked_quest(quest_id=ids["src"], choice_id=choice_a) == ids["a"]
        assert await repo.get_choice_unlocked_quest(quest_id=ids["src"], choice_id=choice_b) == ids["b"]
        unknown = await repo.get_choice_unlocked_quest(
            quest_id=ids["src"], choice_id=f"choice-none-{uuid4().hex[:8]}"
        )
        assert unknown is None
    finally:
        await _delete_ids(graph_db, list(ids.values()))
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_choice_unlocked_quest_returns_none_when_absent() -> None:
    """get_choice_unlocked_quest returns None when the source quest has no matching edge."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    try:
        result = await repo.get_choice_unlocked_quest(
            quest_id=f"q-{uuid4()}", choice_id=f"choice-{uuid4()}"
        )
        assert result is None
    finally:
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jQuestRewardRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_reward_get_quest_state_returns_none_when_absent() -> None:
    """get_quest_state in reward repo returns None for a non-existent quest."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestRewardRepository(graph_db)
    try:
        result = await repo.get_quest_state(
            quest_id=f"q-{uuid4()}", player_id=f"p-{uuid4()}"
        )
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_get_quest_state_returns_seeded_state() -> None:
    """get_quest_state in reward repo decodes the seeded QuestState's reward columns."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestRewardRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    try:
        await _seed_quest_state(
            graph_db,
            quest_id,
            player_id,
            status="completed",
            item_rewards_json='[{"item_id": "potion", "quantity": 2}]',
            currency_reward_json='{"amount": 75}',
            rewards_applied=True,
        )
        result = await repo.get_quest_state(quest_id=quest_id, player_id=player_id)
        assert result is not None
        assert result["quest_id"] == quest_id
        assert result["player_id"] == player_id
        assert result["status"] == "completed"
        assert result["item_rewards"] == [{"item_id": "potion", "quantity": 2}]
        assert result["currency_reward"] == {"amount": 75}
        assert result["rewards_applied"] is True
    finally:
        await _delete_ids(graph_db, [f"{quest_id}:{player_id}"])
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_get_character_balance_returns_seeded_balance() -> None:
    """get_character_balance returns the stored balance, 0 when unset, and None when absent."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestRewardRepository(graph_db)
    funded = f"char-{uuid4().hex[:8]}"
    unfunded = f"char-{uuid4().hex[:8]}"
    try:
        await _seed_character(graph_db, funded, 250)
        await _seed_character(graph_db, unfunded, None)
        assert await repo.get_character_balance(character_id=funded) == 250
        assert await repo.get_character_balance(character_id=unfunded) == 0
        assert await repo.get_character_balance(character_id=f"char-{uuid4()}") is None
    finally:
        await _delete_ids(graph_db, [funded, unfunded])
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_get_character_balance_returns_none_when_absent() -> None:
    """get_character_balance returns None for a character with no currency node."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestRewardRepository(graph_db)
    try:
        result = await repo.get_character_balance(character_id=f"char-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_emit_lifecycle_event_writes_event_node() -> None:
    """emit_lifecycle_event in reward repo persists an Event node."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestRewardRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    event = _test_event(quest_id, player_id, uuid4().hex[:8])
    try:
        await repo.emit_lifecycle_event(event_node=event)
        async with graph_db.get_session() as session:
            result = await session.run(
                "MATCH (e:Event {id: $id}) RETURN e.id AS id", id=event.id
            )
            row = await result.single()
        assert row is not None
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (e:Event {id: $id}) DETACH DELETE e", id=event.id)
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_apply_rewards_atomic_empty_rewards() -> None:
    """apply_rewards_atomic with no item/currency rewards persists state and event."""
    graph_db = _make_graph_db()
    settings = Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")
    repo = Neo4jQuestRewardRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    request_suffix = uuid4().hex[:8]
    event = _test_event(quest_id, player_id, request_suffix)
    state_dict = {
        "reward_source_id": "system",
        "objectives": [],
        "item_rewards": [],
        "currency_reward": None,
    }
    next_state = _state(quest_id, player_id, "completed")
    try:
        stored = await repo.apply_rewards_atomic(
            quest_id=quest_id,
            player_id=player_id,
            request_id=f"req-{request_suffix}",
            state_dict=state_dict,
            next_state_payload=next_state,
            event_node=event,
            settings=settings,
        )
        assert stored["status"] == "completed"
        assert stored["quest_id"] == quest_id
    finally:
        async with graph_db.get_session() as session:
            await session.run(
                "MATCH (n) WHERE n.id IN [$qs, $ev] DETACH DELETE n",
                qs=f"{quest_id}:{player_id}",
                ev=event.id,
            )
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_reward_apply_rewards_atomic_transfers_currency() -> None:
    """apply_rewards_atomic moves the currency reward source -> player and persists state."""
    graph_db = _make_graph_db()
    settings = Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")
    repo = Neo4jQuestRewardRepository(graph_db)
    quest_id = f"q-{uuid4().hex[:8]}"
    player_id = f"p-{uuid4().hex[:8]}"
    giver_id = f"npc-{uuid4().hex[:8]}"
    suffix = uuid4().hex[:8]
    event = _test_event(quest_id, player_id, suffix)
    state_dict = {
        "reward_source_id": giver_id,
        "objectives": [],
        "item_rewards": [],
        "currency_reward": {"amount": 30},
    }
    try:
        await _seed_character(graph_db, giver_id, 100)
        await _seed_character(graph_db, player_id, 5)
        stored = await repo.apply_rewards_atomic(
            quest_id=quest_id,
            player_id=player_id,
            request_id=f"req-{suffix}",
            state_dict=state_dict,
            next_state_payload=_state(quest_id, player_id, "completed"),
            event_node=event,
            settings=settings,
        )
        assert stored["status"] == "completed"
        assert await repo.get_character_balance(character_id=giver_id) == 70
        assert await repo.get_character_balance(character_id=player_id) == 35
        persisted = await repo.get_quest_state(quest_id=quest_id, player_id=player_id)
        assert persisted is not None
        assert persisted["status"] == "completed"
    finally:
        await _delete_ids(
            graph_db, [giver_id, player_id, f"{quest_id}:{player_id}", event.id]
        )
        await graph_db.close()
