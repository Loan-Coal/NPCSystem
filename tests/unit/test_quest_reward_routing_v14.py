"""
test_quest_reward_routing_v14.py - Unit tests for P3 quest reward coordinator routing.

Does NOT: execute real graph writes. All graph calls go through mock QuestRewardGraphPort.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestTransitionMeta
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
        request_id="req-quest-r1",
        actor_id="player-1",
        reason="quest_reward",
        idempotency_key="idem-quest-r1",
        idempotency_request_hash="hash-quest-r1",
    )


def _make_reward_repo(state: dict | None = None, atomic_result: dict | None = None) -> Any:
    """Return a mock QuestRewardGraphPort."""
    repo = MagicMock()

    async def _get_quest_state(*, quest_id: str, player_id: str) -> dict | None:
        return state

    async def _apply_rewards_atomic(
        *, quest_id, player_id, request_id, state_dict, next_state_payload, event_node, settings
    ) -> dict:
        return atomic_result or {**next_state_payload, "rewards_applied": True}

    repo.get_quest_state = _get_quest_state
    repo.apply_rewards_atomic = AsyncMock(side_effect=_apply_rewards_atomic)
    repo.emit_lifecycle_event = AsyncMock()
    repo.get_character_balance = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_apply_rewards_routes_item_and_currency_through_graph_writer() -> None:
    """apply_rewards must delegate to apply_rewards_atomic on the reward repo."""
    state_payload = {
        "quest_id": "quest-2",
        "player_id": "player-1",
        "status": "completed",
        "title": "Delivery",
        "reward_source_id": "system",
        "objectives": [{"objective_id": "obj-1", "target_count": 1}],
        "objective_progress": {"obj-1": 1},
        "item_rewards": [{"item_id": "item-1", "quantity": 2}],
        "currency_reward": {"amount": 25},
        "rewards_applied": False,
    }
    expected_result = {**state_payload, "rewards_applied": True}
    reward_repo = _make_reward_repo(state=state_payload, atomic_result=expected_result)

    reward_router = QuestRewardRouter(
        settings=_settings(),
        registry=_fake_registry(),
        quest_reward_repo=reward_repo,
    )
    result = await reward_router.apply_rewards(
        quest_id="quest-2",
        player_id="player-1",
        meta=_meta(),
    )

    assert result["rewards_applied"] is True
    reward_repo.apply_rewards_atomic.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_rewards_rejects_non_completed_quest() -> None:
    """apply_rewards must raise QuestTransitionError when quest status is not completed."""
    state_payload = {
        "quest_id": "quest-3",
        "player_id": "player-1",
        "status": "in_progress",
        "title": "Delivery",
        "reward_source_id": "system",
        "objectives": [{"objective_id": "obj-1", "target_count": 2}],
        "objective_progress": {"obj-1": 1},
        "item_rewards": [],
        "currency_reward": None,
        "rewards_applied": False,
    }
    reward_repo = _make_reward_repo(state=state_payload)

    reward_router = QuestRewardRouter(
        settings=_settings(),
        registry=_fake_registry(),
        quest_reward_repo=reward_repo,
    )
    with pytest.raises(QuestTransitionError):
        await reward_router.apply_rewards(
            quest_id="quest-3",
            player_id="player-1",
            meta=_meta(),
        )


@pytest.mark.asyncio
async def test_apply_rewards_aggregates_duplicate_item_rewards() -> None:
    """apply_rewards_atomic is called with the correct state_dict containing duplicate items."""
    state_payload = {
        "quest_id": "quest-4",
        "player_id": "player-1",
        "status": "completed",
        "title": "Bundle delivery",
        "reward_source_id": "system",
        "objectives": [{"objective_id": "obj-1", "target_count": 1}],
        "objective_progress": {"obj-1": 1},
        "item_rewards": [
            {"item_id": "item-bundle", "quantity": 1},
            {"item_id": "item-bundle", "quantity": 2},
        ],
        "currency_reward": None,
        "rewards_applied": False,
    }
    expected_result = {**state_payload, "rewards_applied": True}
    reward_repo = _make_reward_repo(state=state_payload, atomic_result=expected_result)

    reward_router = QuestRewardRouter(
        settings=_settings(),
        registry=_fake_registry(),
        quest_reward_repo=reward_repo,
    )
    result = await reward_router.apply_rewards(
        quest_id="quest-4",
        player_id="player-1",
        meta=_meta(),
    )

    reward_repo.apply_rewards_atomic.assert_awaited_once()
    call_kwargs = reward_repo.apply_rewards_atomic.call_args.kwargs
    state_dict = call_kwargs["state_dict"]
    assert any(r["item_id"] == "item-bundle" for r in state_dict["item_rewards"])
    assert result["rewards_applied"] is True


@pytest.mark.asyncio
async def test_apply_rewards_rejects_empty_reward_source() -> None:
    """apply_rewards must raise QuestTransitionError when reward_source_id is empty."""
    state_payload = {
        "quest_id": "quest-5",
        "player_id": "player-1",
        "status": "completed",
        "title": "Delivery",
        "reward_source_id": "",
        "objectives": [{"objective_id": "obj-1", "target_count": 1}],
        "objective_progress": {"obj-1": 1},
        "item_rewards": [],
        "currency_reward": None,
        "rewards_applied": False,
    }
    reward_repo = _make_reward_repo(state=state_payload)

    reward_router = QuestRewardRouter(
        settings=_settings(),
        registry=_fake_registry(),
        quest_reward_repo=reward_repo,
    )
    with pytest.raises(QuestTransitionError) as error:
        await reward_router.apply_rewards(
            quest_id="quest-5",
            player_id="player-1",
            meta=_meta(),
        )

    assert error.value.code == "QUEST_REWARD_SOURCE_INVALID"
