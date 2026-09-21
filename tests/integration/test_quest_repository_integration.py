"""
test_quest_repository_integration.py — Integration tests for Neo4jQuestLifecycleRepository,
Neo4jQuestOfferRepository, Neo4jQuestChainRepository, and Neo4jQuestRewardRepository.

Covers 15 public methods T11.2 identified as having no unit-or-integration path. The existing
test_quest_lifecycle_integration_v14 exercises the engine layer; this file exercises the
repository layer directly against real Cypher.

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
async def test_quest_lifecycle_get_world_state_returns_world_state() -> None:
    """get_world_state returns a WorldState instance from the lifecycle repository."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestLifecycleRepository(graph_db)
    try:
        result = await repo.get_world_state()
        assert isinstance(result, WorldState)
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
async def test_quest_chain_get_unlocked_quests_returns_empty() -> None:
    """get_unlocked_quests returns an empty list when no UNLOCKS edges exist."""
    graph_db = _make_graph_db()
    repo = Neo4jQuestChainRepository(graph_db)
    try:
        result = await repo.get_unlocked_quests(
            quest_id=f"q-{uuid4()}", outcome="completed"
        )
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_quest_chain_get_choice_unlocked_quest_returns_none() -> None:
    """get_choice_unlocked_quest returns None when no CHOICE_UNLOCKS edge exists."""
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
