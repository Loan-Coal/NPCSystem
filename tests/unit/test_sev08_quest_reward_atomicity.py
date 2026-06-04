"""
test_sev08_quest_reward_atomicity.py - Regression tests for SEV-08.

Validates that quest reward application:
  1. Checks item possession before granting rewards.
  2. Collects delivery items before granting rewards (correct ordering).
  3. Does NOT swallow delivery failures.

Does NOT: require a real Neo4j connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from npc_engine.config import Settings
from npc_engine.engines.quest.models import (
    QuestObjectiveInput,
    QuestRewardCurrency,
    QuestRewardItem,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
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


@dataclass
class _FakeTx:
    committed: bool = False
    rolled_back: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self) -> None:
        self._tx = _FakeTx()

    async def begin_transaction(self) -> _FakeTx:
        return self._tx


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


@pytest.mark.asyncio
async def test_apply_rewards_raises_when_delivery_item_not_possessed(monkeypatch) -> None:
    """Possession check failure raises QuestTransitionError before any transfer is attempted."""
    state_store = {"quest-deliver-1": {"player-1": _deliver_quest_state()}}

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return state_store.get(quest_id, {}).get(player_id)

    async def fake_check_possession(tx, *, player_id: str, item_id: str, min_quantity: int) -> bool:
        return False  # player does not have the item

    transfer_calls: list[dict] = []

    async def fake_execute_item_transfer(tx, *, source_id, destination_id, item_id, quantity, reason, request_id, idempotency_key, transfer_kind):
        transfer_calls.append({"source_id": source_id, "transfer_kind": transfer_kind})
        return {"item_id": item_id, "quantity": quantity, "replayed": False, "request_id": request_id}

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.check_item_possession_in_tx", fake_check_possession)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.execute_item_transfer_in_tx", fake_execute_item_transfer)

    engine = QuestLifecycleEngine(settings=_settings(), registry=_fake_registry())
    with pytest.raises(QuestTransitionError) as exc:
        await engine.apply_rewards(
            session=_FakeSession(),  # type: ignore[arg-type]
            quest_id="quest-deliver-1",
            player_id="player-1",
            meta=_meta(),
        )

    assert exc.value.code == "QUEST_ITEM_NOT_POSSESSED"
    assert transfer_calls == [], "No transfers should occur when possession check fails"


@pytest.mark.asyncio
async def test_apply_rewards_delivery_collected_before_reward_grants(monkeypatch) -> None:
    """Delivery item is collected before reward items are granted."""
    state_store = {"quest-deliver-1": {"player-1": _deliver_quest_state()}}
    call_order: list[str] = []

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return state_store.get(quest_id, {}).get(player_id)

    async def fake_upsert_quest_state(*, session, quest_id: str, player_id: str, state_payload: dict):
        state_store[quest_id][player_id] = state_payload
        return state_payload

    async def fake_event_write(*, tx, event):
        return None

    async def fake_check_possession(tx, *, player_id: str, item_id: str, min_quantity: int) -> bool:
        return True

    async def fake_execute_item_transfer(tx, *, source_id, destination_id, item_id, quantity, reason, request_id, idempotency_key, transfer_kind):
        call_order.append(transfer_kind)
        return {"item_id": item_id, "quantity": quantity, "replayed": False, "request_id": request_id}

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_lifecycle_event", fake_event_write)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.check_item_possession_in_tx", fake_check_possession)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.execute_item_transfer_in_tx", fake_execute_item_transfer)

    engine = QuestLifecycleEngine(settings=_settings(), registry=_fake_registry())
    result = await engine.apply_rewards(
        session=_FakeSession(),  # type: ignore[arg-type]
        quest_id="quest-deliver-1",
        player_id="player-1",
        meta=_meta(),
    )

    assert result["rewards_applied"] is True
    assert "quest_deliver" in call_order, "Delivery transfer must be called"
    assert "quest_reward" in call_order, "Reward transfer must be called"
    delivery_idx = call_order.index("quest_deliver")
    reward_idx = call_order.index("quest_reward")
    assert delivery_idx < reward_idx, "Delivery must be collected BEFORE reward is granted"


@pytest.mark.asyncio
async def test_apply_rewards_delivery_failure_not_swallowed(monkeypatch) -> None:
    """A failed delivery transfer raises QuestTransitionError; rewards are NOT granted."""
    from npc_engine.utils.errors import ItemTransferValidationError

    state_store = {"quest-deliver-1": {"player-1": _deliver_quest_state()}}
    reward_granted = {"called": False}

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return state_store.get(quest_id, {}).get(player_id)

    async def fake_check_possession(tx, *, player_id: str, item_id: str, min_quantity: int) -> bool:
        return True

    async def fake_execute_item_transfer(tx, *, source_id, destination_id, item_id, quantity, reason, request_id, idempotency_key, transfer_kind):
        if transfer_kind == "quest_deliver":
            raise ItemTransferValidationError(code="ITEM_TRANSFER_FAILED", detail="item not owned")
        reward_granted["called"] = True
        return {"item_id": item_id, "quantity": quantity, "replayed": False, "request_id": request_id}

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.check_item_possession_in_tx", fake_check_possession)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.execute_item_transfer_in_tx", fake_execute_item_transfer)

    engine = QuestLifecycleEngine(settings=_settings(), registry=_fake_registry())
    with pytest.raises(QuestTransitionError) as exc:
        await engine.apply_rewards(
            session=_FakeSession(),  # type: ignore[arg-type]
            quest_id="quest-deliver-1",
            player_id="player-1",
            meta=_meta(),
        )

    assert exc.value.code in {"QUEST_ITEM_NOT_POSSESSED", "QUEST_DELIVER_FAILED"}
    assert reward_granted["called"] is False, "Reward must NOT be granted when delivery fails"
