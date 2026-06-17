"""
test_quest_lifecycle_engine_v14.py - Unit tests for P3 quest lifecycle transitions.

Does NOT: execute real Neo4j writes. All graph calls go through mock ports.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestObjectiveInput, QuestRewardCurrency, QuestRewardItem, QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.engines.quest.quest_offer_service import QuestOfferService
from npc_engine.engines.quest.quest_reward_router import QuestRewardRouter
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


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
        request_id="req-quest-1",
        actor_id="player-1",
        reason="story_progression",
        idempotency_key="idem-quest-1",
        idempotency_request_hash="hash-quest-1",
    )


# ---------------------------------------------------------------------------
# Mock repo factories
# ---------------------------------------------------------------------------


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


def _make_offer_repo(state_store: dict, quest_node: dict | None = None) -> Any:
    """Return a mock QuestOfferGraphPort backed by an in-memory store."""
    repo = MagicMock()

    repo.get_quest = AsyncMock(return_value=quest_node)
    repo.update_quest_node_status = AsyncMock()

    async def _offer_quest_atomic(
        *, quest_id: str, player_id: str, state_payload: dict, event_node: Any
    ) -> dict:
        key = (quest_id, player_id)
        if key not in state_store:
            state_store[key] = dict(state_payload)
        return dict(state_store[key])

    repo.offer_quest_atomic = _offer_quest_atomic
    return repo


def _make_reward_repo(state_store: dict) -> Any:
    """Return a mock QuestRewardGraphPort backed by an in-memory store."""
    repo = MagicMock()

    async def _get_quest_state(*, quest_id: str, player_id: str) -> dict | None:
        return state_store.get((quest_id, player_id))

    async def _apply_rewards_atomic(
        *, quest_id, player_id, request_id, state_dict, next_state_payload, event_node, settings
    ) -> dict:
        state_store[(quest_id, player_id)] = dict(next_state_payload)
        return dict(next_state_payload)

    repo.get_quest_state = _get_quest_state
    repo.apply_rewards_atomic = _apply_rewards_atomic
    repo.emit_lifecycle_event = AsyncMock()
    repo.get_character_balance = AsyncMock(return_value=None)
    return repo


# ---------------------------------------------------------------------------
# F3.4: memory engine injection
# ---------------------------------------------------------------------------


def test_memory_engine_is_injected_when_provided() -> None:
    """F3.4: the injected MemoryEngine is stored and used (DIP composition root)."""
    from npc_engine.engines.memory.memory_engine import MemoryEngine

    sentinel = MemoryEngine(memory_repo=object())  # type: ignore[arg-type]
    repo = _make_lifecycle_repo({})
    engine = QuestLifecycleEngine(
        settings=_settings(), registry=_fake_registry(), memory_engine=sentinel, quest_repo=repo,
    )
    assert engine._memory_engine is sentinel


def test_memory_engine_is_none_when_omitted() -> None:
    """Omitting memory_engine leaves it None — commitment-memory formation is skipped."""
    repo = _make_lifecycle_repo({})
    engine = QuestLifecycleEngine(
        settings=_settings(), registry=_fake_registry(), quest_repo=repo,
    )
    assert engine._memory_engine is None


# ---------------------------------------------------------------------------
# Happy path integration: offer → accept → update → evaluate → apply_rewards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_accept_update_evaluate_and_apply_rewards_happy_path() -> None:
    state_store: dict = {}

    offer_repo = _make_offer_repo(state_store)
    lifecycle_repo = _make_lifecycle_repo(state_store)
    reward_repo = _make_reward_repo(state_store)

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    engine = QuestLifecycleEngine(
        settings=_settings(), registry=_fake_registry(), quest_repo=lifecycle_repo,
    )
    reward_router = QuestRewardRouter(
        settings=_settings(), registry=_fake_registry(), quest_reward_repo=reward_repo,
    )

    offered = await offer_service.offer_quest(
        quest_id="quest-1",
        player_id="player-1",
        title="Collect herbs",
        objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=2)],
        item_rewards=[QuestRewardItem(item_id="herb-pouch", quantity=1)],
        currency_reward=QuestRewardCurrency(amount=15),
        meta=_meta(),
    )
    assert offered["status"] == "offered"

    accepted = await engine.accept_quest(
        quest_id="quest-1", player_id="player-1", meta=_meta(),
    )
    assert accepted["status"] == "accepted"

    in_progress = await engine.update_objective(
        quest_id="quest-1", player_id="player-1",
        objective_id="obj-1", progress_delta=1, meta=_meta(),
    )
    assert in_progress["status"] == "in_progress"

    await engine.update_objective(
        quest_id="quest-1", player_id="player-1",
        objective_id="obj-1", progress_delta=1, meta=_meta(),
    )
    completed = await engine.evaluate_completion(
        quest_id="quest-1", player_id="player-1", meta=_meta(),
    )
    assert completed["status"] == "completed"

    reward_result = await reward_router.apply_rewards(
        quest_id="quest-1", player_id="player-1", meta=_meta(),
    )
    assert reward_result["status"] == "completed"
    assert reward_result["rewards_applied"] is True


# ---------------------------------------------------------------------------
# accept_quest requires offered state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_requires_offered_state() -> None:
    repo = _make_lifecycle_repo({})
    engine = QuestLifecycleEngine(
        settings=_settings(), registry=_fake_registry(), quest_repo=repo,
    )
    with pytest.raises(QuestTransitionError):
        await engine.accept_quest(
            quest_id="quest-404", player_id="player-1", meta=_meta(),
        )


# ---------------------------------------------------------------------------
# offer_quest rejects empty reward_source_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_rejects_existing_offered_state_with_empty_reward_source() -> None:
    """offer_quest rejects a stored state whose reward_source_id is empty."""
    state_store: dict = {}

    offer_repo = _make_offer_repo(state_store)

    async def _offer_quest_atomic_with_empty_source(
        *, quest_id: str, player_id: str, state_payload: dict, event_node: Any
    ) -> dict:
        return {
            **state_payload,
            "reward_source_id": "",
        }

    offer_repo.offer_quest_atomic = _offer_quest_atomic_with_empty_source

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    with pytest.raises(QuestTransitionError) as error:
        await offer_service.offer_quest(
            quest_id="quest-1",
            player_id="player-1",
            title="Collect herbs",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )

    assert error.value.code == "QUEST_REWARD_SOURCE_INVALID"


# ---------------------------------------------------------------------------
# apply_rewards emits provenance event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_rewards_emits_provenance_event_with_transaction_support() -> None:
    """apply_rewards must call apply_rewards_atomic with the meta provenance fields."""
    state_store: dict = {
        ("quest-6", "player-1"): {
            "quest_id": "quest-6",
            "player_id": "player-1",
            "status": "completed",
            "reward_source_id": "system",
            "title": "Deliver package",
            "objectives": [{"objective_id": "obj-1", "target_count": 1}],
            "objective_progress": {"obj-1": 1},
            "item_rewards": [{"item_id": "satchel", "quantity": 1}],
            "currency_reward": None,
            "rewards_applied": False,
        }
    }
    captured_event: dict = {}

    async def _apply_rewards_atomic(
        *, quest_id, player_id, request_id, state_dict, next_state_payload, event_node, settings
    ) -> dict:
        captured_event["event"] = event_node
        return {**next_state_payload, "rewards_applied": True}

    reward_repo = _make_reward_repo(state_store)
    reward_repo.apply_rewards_atomic = AsyncMock(side_effect=_apply_rewards_atomic)

    reward_router = QuestRewardRouter(
        settings=_settings(), registry=_fake_registry(), quest_reward_repo=reward_repo,
    )
    await reward_router.apply_rewards(
        quest_id="quest-6", player_id="player-1", meta=_meta(),
    )

    event = captured_event["event"]
    assert event.provenance["request_id"] == "req-quest-1"
    assert event.provenance["idempotency_key"] == "idem-quest-1"
    assert event.provenance["idempotency_request_hash"] == "hash-quest-1"


# ---------------------------------------------------------------------------
# offer_quest_atomic raises → exception propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_rolls_back_state_when_event_write_fails() -> None:
    """When offer_quest_atomic raises, the exception propagates out of offer_quest."""
    state_store: dict = {}
    offer_repo = _make_offer_repo(state_store)

    async def _failing_atomic(
        *, quest_id: str, player_id: str, state_payload: dict, event_node: Any
    ) -> dict:
        raise RuntimeError("event write failure")

    offer_repo.offer_quest_atomic = _failing_atomic

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    with pytest.raises(RuntimeError, match="event write failure"):
        await offer_service.offer_quest(
            quest_id="quest-rollback-1",
            player_id="player-1",
            title="Deliver package",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )

    assert ("quest-rollback-1", "player-1") not in state_store


# ---------------------------------------------------------------------------
# offer_draft_quest tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_draft_quest_happy_path() -> None:
    """offer_draft_quest transitions a draft Quest node to offered and creates QuestState."""
    state_store: dict = {}
    offer_repo = _make_offer_repo(state_store, quest_node={"status": "draft", "id": "quest-draft-1"})

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    state = await offer_service.offer_draft_quest(
        quest_id="quest-draft-1",
        player_id="player-1",
        title="Deliver Herbs",
        objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
        item_rewards=[],
        currency_reward=None,
        meta=_meta(),
    )

    assert state["status"] == "offered"
    offer_repo.update_quest_node_status.assert_awaited_once()
    call_kwargs = offer_repo.update_quest_node_status.call_args.kwargs
    assert call_kwargs["status"] == "offered"


@pytest.mark.asyncio
async def test_offer_draft_quest_non_draft_raises() -> None:
    """offer_draft_quest rejects a Quest node that is not in draft status."""
    state_store: dict = {}
    offer_repo = _make_offer_repo(state_store, quest_node={"status": "offered", "id": "quest-x"})

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    with pytest.raises(QuestTransitionError) as exc:
        await offer_service.offer_draft_quest(
            quest_id="quest-already-offered",
            player_id="player-1",
            title="Some Quest",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )
    assert exc.value.code == "QUEST_TRANSITION_INVALID"


@pytest.mark.asyncio
async def test_offer_draft_quest_not_found_raises() -> None:
    """offer_draft_quest raises QUEST_NOT_FOUND when the Quest node does not exist."""
    state_store: dict = {}
    offer_repo = _make_offer_repo(state_store, quest_node=None)

    offer_service = QuestOfferService(
        settings=_settings(), registry=_fake_registry(), quest_offer_repo=offer_repo,
    )
    with pytest.raises(QuestTransitionError) as exc:
        await offer_service.offer_draft_quest(
            quest_id="quest-missing",
            player_id="player-1",
            title="Some Quest",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )
    assert exc.value.code == "QUEST_NOT_FOUND"


# ---------------------------------------------------------------------------
# fail_quest tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fail_quest_transitions_to_failed_and_calls_chain_resolver() -> None:
    """fail_quest must persist FAILED status and invoke chain_resolver with outcome 'fail'."""
    state_store: dict = {
        ("quest-f1", "player-1"): {
            "quest_id": "quest-f1",
            "player_id": "player-1",
            "status": "in_progress",
            "reward_source_id": "system",
            "title": "Risky errand",
            "objectives": [],
            "objective_progress": {},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }
    }

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    lifecycle_repo = _make_lifecycle_repo(state_store)
    engine = QuestLifecycleEngine(
        settings=_settings(),
        registry=_fake_registry(),
        chain_resolver=resolver,
        quest_repo=lifecycle_repo,
    )
    stored = await engine.fail_quest(
        quest_id="quest-f1", player_id="player-1", meta=_meta(),
    )

    assert stored["status"] == "failed"
    resolver.resolve.assert_awaited_once()
    call_kwargs = resolver.resolve.call_args.kwargs
    assert call_kwargs["quest_id"] == "quest-f1"
    assert call_kwargs["player_id"] == "player-1"
    assert call_kwargs["outcome"] == "fail"


@pytest.mark.asyncio
async def test_fail_quest_raises_on_terminal_status() -> None:
    """fail_quest must raise QuestTransitionError when quest is already terminal."""
    state_store: dict = {
        ("quest-done", "player-1"): {
            "quest_id": "quest-done",
            "player_id": "player-1",
            "status": "completed",
            "reward_source_id": "system",
            "title": "Done quest",
            "objectives": [],
            "objective_progress": {},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }
    }
    lifecycle_repo = _make_lifecycle_repo(state_store)
    engine = QuestLifecycleEngine(
        settings=_settings(), registry=_fake_registry(), quest_repo=lifecycle_repo,
    )
    with pytest.raises(QuestTransitionError) as exc:
        await engine.fail_quest(
            quest_id="quest-done", player_id="player-1", meta=_meta(),
        )
    assert exc.value.code == "QUEST_TRANSITION_INVALID"
