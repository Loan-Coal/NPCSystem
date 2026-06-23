"""
Module: test_quest_chain_resolver
Layer: tests (unit)
Purpose: Unit tests for QuestChainResolver — verifies chain resolution, no-op on empty
    chain, outcome propagation, lifecycle engine integration, and choice-based branching
    (EXP-218: choose() selects matching on_choice_id successor; null on_choice_id auto-unlocks).
Dependencies: npc_engine.engines.quest.quest_chain_resolver,
    npc_engine.engines.quest.quest_lifecycle_engine,
    npc_engine.engines.quest.models, unittest.mock
Used by: pytest (make test)

Does NOT: touch Neo4j, call the LLM, or exercise real graph queries.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.type_registry.contracts import TypeRegistry


class _FakeEventModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = ""
    summary: str = ""
    provenance: dict = {}


def _fake_registry() -> TypeRegistry:
    return TypeRegistry(schema_version="1.0", node_models={"event": _FakeEventModel})


def _settings() -> Settings:
    return Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")


def _meta() -> QuestTransitionMeta:
    return QuestTransitionMeta(
        request_id="req-chain-1",
        actor_id="player-1",
        reason="chain_test",
        idempotency_key="idem-chain-1",
        idempotency_request_hash="hash-chain-1",
    )


def _make_chain_repo(
    unlocked: list[str] | None = None,
    choice_unlock: str | None = None,
) -> Any:
    """Return a mock QuestChainGraphPort with configurable return values."""
    repo = MagicMock()
    repo.get_unlocked_quests = AsyncMock(return_value=unlocked or [])
    repo.get_choice_unlocked_quest = AsyncMock(return_value=choice_unlock)
    return repo


def _make_lifecycle_repo(state_store: dict) -> Any:
    """Return a mock QuestLifecycleGraphPort backed by an in-memory store."""
    from npc_engine.world.world_state import WorldState

    repo = MagicMock()

    async def _get_quest_state(*, quest_id: str, player_id: str) -> dict | None:
        return state_store.get((quest_id, player_id))

    async def _persist_state_and_event(
        *, quest_id: str, player_id: str, state_payload: dict, event_node: Any
    ) -> dict:
        state_store[(quest_id, player_id)] = dict(state_payload)
        return dict(state_payload)

    repo.get_quest_state = _get_quest_state
    repo.persist_state_and_event = _persist_state_and_event
    repo.emit_lifecycle_event = AsyncMock()
    repo.update_quest_node_status = AsyncMock()
    repo.get_world_state = AsyncMock(return_value=WorldState(
        id="world", year=1, season="spring", day=1, time_of_day="morning",
    ))
    return repo


# ---------------------------------------------------------------------------
# Test 1 — happy path: UNLOCKS edge found → offer_quest called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_offers_next_quest_on_complete() -> None:
    """When get_unlocked_quests returns one next quest, offer_quest is called for it."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo(unlocked=["quest_b"])
    resolver = QuestChainResolver(offer_service=offer_service, chain_repo=chain_repo)

    await resolver.resolve(quest_id="quest_a", player_id="player_demo", outcome="complete")

    offer_service.offer_quest.assert_awaited_once_with(
        next_quest_id="quest_b",
        player_id="player_demo",
    )


# ---------------------------------------------------------------------------
# Test 2 — no chain: empty list → offer_quest NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_no_op_when_no_chain() -> None:
    """When get_unlocked_quests returns empty list, offer_quest is not called."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo(unlocked=[])
    resolver = QuestChainResolver(offer_service=offer_service, chain_repo=chain_repo)

    await resolver.resolve(quest_id="quest_a", player_id="player_demo", outcome="complete")

    offer_service.offer_quest.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 3 — fail outcome: correct on_outcome passed to get_unlocked_quests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_passes_fail_outcome() -> None:
    """resolver.resolve(..., outcome='fail') passes outcome='fail' to chain_repo."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo(unlocked=["quest_c"])
    resolver = QuestChainResolver(offer_service=offer_service, chain_repo=chain_repo)

    await resolver.resolve(quest_id="quest_a", player_id="player_demo", outcome="fail")

    chain_repo.get_unlocked_quests.assert_awaited_once_with(
        quest_id="quest_a",
        outcome="fail",
    )


# ---------------------------------------------------------------------------
# Test 4 — lifecycle engine calls resolver on COMPLETED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifecycle_engine_calls_resolver_on_completion() -> None:
    """QuestLifecycleEngine with chain_resolver calls resolver.resolve after COMPLETED transition."""
    state_store: dict = {
        ("quest_a", "player_demo"): {
            "quest_id": "quest_a",
            "player_id": "player_demo",
            "reward_source_id": "system",
            "title": "Patrol Duty",
            "status": "in_progress",
            "objectives": [
                {
                    "objective_id": "obj_1",
                    "target_count": 1,
                    "objective_type": "deliver",
                    "target_id": None,
                }
            ],
            "objective_progress": {"obj_1": 1},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }
    }

    mock_resolver = MagicMock()
    mock_resolver.resolve = AsyncMock(return_value=None)

    lifecycle_repo = _make_lifecycle_repo(state_store)
    engine = QuestLifecycleEngine(
        settings=_settings(),
        registry=_fake_registry(),
        chain_resolver=mock_resolver,
        quest_repo=lifecycle_repo,
    )

    await engine.evaluate_completion(
        quest_id="quest_a",
        player_id="player_demo",
        meta=_meta(),
    )

    mock_resolver.resolve.assert_awaited_once_with(
        quest_id="quest_a",
        player_id="player_demo",
        outcome="complete",
    )


# ---------------------------------------------------------------------------
# EXP-218 — Test 5: choose() selects the matching on_choice_id successor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_choose_selects_matching_successor() -> None:
    """choose() calls get_choice_unlocked_quest with choice_id and offers the match."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo(choice_unlock="quest_branch_b")
    resolver = QuestChainResolver(offer_service=offer_service, chain_repo=chain_repo)

    result = await resolver.choose(
        quest_id="quest_a",
        player_id="player_demo",
        choice_id="choice_help",
    )

    offer_service.offer_quest.assert_awaited_once_with(
        next_quest_id="quest_branch_b",
        player_id="player_demo",
    )
    assert result == "quest_branch_b"


# ---------------------------------------------------------------------------
# EXP-218 — Test 6: null on_choice_id auto-unlocks (back-compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_choice_auto_unlocks() -> None:
    """choose() with no matching on_choice_id returns None without calling offer_quest."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo(choice_unlock=None)
    resolver = QuestChainResolver(offer_service=offer_service, chain_repo=chain_repo)

    result = await resolver.choose(
        quest_id="quest_a",
        player_id="player_demo",
        choice_id="choice_unknown",
    )

    offer_service.offer_quest.assert_not_awaited()
    assert result is None
