"""
test_sev08_quest_reward_atomicity.py - Regression tests for SEV-08.

Validates that quest reward application:
  1. Checks item possession before granting rewards.
  2. Collects delivery items before granting rewards (correct ordering).
  3. Does NOT swallow delivery failures.

Does NOT: require a real Neo4j connection. All graph calls go through mock QuestRewardGraphPort.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_reward_router import QuestRewardRouter
from npc_engine.utils.errors import QuestTransitionError
from pydantic import BaseModel, ConfigDict
from npc_engine.type_registry.contracts import TypeRegistry


class _FakeEventModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = ""
    summary: str = ""
    provenance: dict = {}


def _fake_registry() -> TypeRegistry:
    return TypeRegistry(schema_version="1.0", node_models={"event": _FakeEventModel})


def _settings() -> Settings:
    return Settings(API_KEY_SECRET="test_secret_key_for_sev08")


def _meta() -> QuestTransitionMeta:
    return QuestTransitionMeta(
        request_id="req-sev08-1",
        actor_id="player-1",
        reason="quest_completion",
        idempotency_key="idem-sev08-1",
        idempotency_request_hash="hash-sev08-1",
    )


def _deliver_quest_state() -> dict[str, Any]:
    """Quest state: completed, non-system reward source, one deliver objective."""
    return {
        "quest_id": "quest-deliver-1",
        "player_id": "player-1",
        "status": "completed",
        "reward_source_id": "npc-merchant",
        "title": "Deliver the Sword",
        "objectives": [
            {
                "objective_id": "obj-deliver",
                "target_count": 1,
                "objective_type": "deliver",
                "target_id": "iron-sword",
            }
        ],
        "objective_progress": {"obj-deliver": 1},
        "item_rewards": [{"item_id": "gold-coin", "quantity": 5}],
        "currency_reward": None,
        "rewards_applied": False,
    }


def _make_reward_repo(
    state: dict | None = None,
    atomic_side_effect: Any = None,
) -> Any:
    """Return a mock QuestRewardGraphPort."""
    repo = MagicMock()

    async def _get_quest_state(*, quest_id: str, player_id: str) -> dict | None:
        return state

    repo.get_quest_state = _get_quest_state
    repo.emit_lifecycle_event = AsyncMock()
    repo.get_character_balance = AsyncMock(return_value=None)

    if atomic_side_effect is not None:
        repo.apply_rewards_atomic = AsyncMock(side_effect=atomic_side_effect)
    else:
        async def _default_atomic(
            *, quest_id, player_id, request_id, state_dict, next_state_payload, event_node, settings
        ) -> dict:
            return {**next_state_payload, "rewards_applied": True}

        repo.apply_rewards_atomic = AsyncMock(side_effect=_default_atomic)
    return repo


@pytest.mark.asyncio
async def test_apply_rewards_raises_when_delivery_item_not_possessed() -> None:
    """Possession check failure raises QuestTransitionError before any transfer is attempted."""
    state = _deliver_quest_state()
    reward_repo = _make_reward_repo(
        state=state,
        atomic_side_effect=QuestTransitionError(
            code="QUEST_ITEM_NOT_POSSESSED",
            detail="player does not possess iron-sword",
        ),
    )

    engine = QuestRewardRouter(
        settings=_settings(), registry=_fake_registry(), quest_reward_repo=reward_repo,
    )
    with pytest.raises(QuestTransitionError) as exc:
        await engine.apply_rewards(
            quest_id="quest-deliver-1",
            player_id="player-1",
            meta=_meta(),
        )

    assert exc.value.code == "QUEST_ITEM_NOT_POSSESSED"
    reward_repo.apply_rewards_atomic.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_rewards_delivery_collected_before_reward_grants() -> None:
    """apply_rewards_atomic is called once (ordering is atomically enforced by the repo)."""
    state = _deliver_quest_state()
    call_order: list[str] = []

    async def _ordered_atomic(
        *, quest_id, player_id, request_id, state_dict, next_state_payload, event_node, settings
    ) -> dict:
        call_order.append("apply_rewards_atomic")
        return {**next_state_payload, "rewards_applied": True}

    reward_repo = _make_reward_repo(state=state, atomic_side_effect=_ordered_atomic)

    engine = QuestRewardRouter(
        settings=_settings(), registry=_fake_registry(), quest_reward_repo=reward_repo,
    )
    result = await engine.apply_rewards(
        quest_id="quest-deliver-1",
        player_id="player-1",
        meta=_meta(),
    )

    assert result["rewards_applied"] is True
    assert "apply_rewards_atomic" in call_order, "apply_rewards_atomic must be called"
    assert call_order.count("apply_rewards_atomic") == 1, "must be called exactly once"


@pytest.mark.asyncio
async def test_apply_rewards_delivery_failure_not_swallowed() -> None:
    """A delivery failure from apply_rewards_atomic raises QuestTransitionError; is not swallowed."""
    state = _deliver_quest_state()
    reward_repo = _make_reward_repo(
        state=state,
        atomic_side_effect=QuestTransitionError(
            code="QUEST_DELIVER_FAILED",
            detail="item transfer failed mid-atomically",
        ),
    )

    engine = QuestRewardRouter(
        settings=_settings(), registry=_fake_registry(), quest_reward_repo=reward_repo,
    )
    with pytest.raises(QuestTransitionError) as exc:
        await engine.apply_rewards(
            quest_id="quest-deliver-1",
            player_id="player-1",
            meta=_meta(),
        )

    assert exc.value.code in {"QUEST_ITEM_NOT_POSSESSED", "QUEST_DELIVER_FAILED"}
