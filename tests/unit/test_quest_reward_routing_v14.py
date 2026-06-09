"""
test_quest_reward_routing_v14.py - Unit tests for P3 quest reward coordinator routing.

Does NOT: execute real graph writes.

Dependencies injected: monkeypatched graph writer coordinators.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass
class _FakeTx:
    async def commit(self) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    async def begin_transaction(self):
        return _FakeTx()


def _fake_session() -> _FakeSession:
    return _FakeSession()


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


@pytest.mark.asyncio
async def test_apply_rewards_routes_item_and_currency_through_graph_writer(monkeypatch) -> None:
    state_payload = {
        "quest_id": "quest-2",
        "player_id": "player-1",
        "status": "completed",
        "title": "Delivery",
        "objectives": [{"objective_id": "obj-1", "target_count": 1}],
        "objective_progress": {"obj-1": 1},
        "item_rewards": [{"item_id": "item-1", "quantity": 2}],
        "currency_reward": {"amount": 25},
        "rewards_applied": False,
    }
    called = {"item": 0, "currency": 0}

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return dict(state_payload)

    async def fake_upsert_quest_state(*, session, quest_id: str, player_id: str, state_payload: dict):
        return dict(state_payload)

    async def fake_event_write(*, tx, event):
        return None

    async def fake_item_transfer_in_tx(tx, *, source_id, destination_id, item_id, quantity, reason, request_id, idempotency_key, transfer_kind):
        called["item"] += 1
        return {"request_id": request_id, "item_id": item_id, "quantity": quantity, "replayed": False}

    async def fake_currency_transfer_in_tx(tx, *, settings, source_id, destination_id, amount, reason, request_id, idempotency_key, session_scope, transfer_kind):
        called["currency"] += 1
        assert transfer_kind == "quest_reward"
        return {"request_id": request_id, "amount": amount, "replayed": False}

    async def fake_check_possession(tx, *, player_id, item_id, min_quantity):
        return True

    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.upsert_quest_lifecycle_event", fake_event_write)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.execute_item_transfer_in_tx", fake_item_transfer_in_tx)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.execute_currency_transfer_in_tx", fake_currency_transfer_in_tx)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.check_item_possession_in_tx", fake_check_possession)

    reward_router = QuestRewardRouter(settings=_settings(), registry=_fake_registry())
    result = await reward_router.apply_rewards(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-2",
        player_id="player-1",
        meta=_meta(),
    )

    assert result["rewards_applied"] is True
    assert called["item"] == 1
    assert called["currency"] == 1


@pytest.mark.asyncio
async def test_apply_rewards_rejects_non_completed_quest(monkeypatch) -> None:
    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return {
            "quest_id": quest_id,
            "player_id": player_id,
            "status": "in_progress",
            "title": "Delivery",
            "objectives": [{"objective_id": "obj-1", "target_count": 2}],
            "objective_progress": {"obj-1": 1},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }

    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.get_quest_state", fake_get_quest_state)

    reward_router = QuestRewardRouter(settings=_settings(), registry=_fake_registry())
    with pytest.raises(QuestTransitionError):
        await reward_router.apply_rewards(
            session=_fake_session(),  # type: ignore[arg-type]
            quest_id="quest-3",
            player_id="player-1",
            meta=_meta(),
        )


@pytest.mark.asyncio
async def test_apply_rewards_aggregates_duplicate_item_rewards(monkeypatch) -> None:
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
    item_calls: list[dict] = []

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return dict(state_payload)

    async def fake_upsert_quest_state(*, session, quest_id: str, player_id: str, state_payload: dict):
        return dict(state_payload)

    async def fake_event_write(*, tx, event):
        return None

    async def fake_item_transfer_in_tx(tx, *, source_id, destination_id, item_id, quantity, reason, request_id, idempotency_key, transfer_kind):
        item_calls.append({"item_id": item_id, "quantity": quantity, "transfer_kind": transfer_kind})
        return {"request_id": request_id, "item_id": item_id, "quantity": quantity, "replayed": False}

    async def fake_check_possession(tx, *, player_id, item_id, min_quantity):
        return True

    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.upsert_quest_lifecycle_event", fake_event_write)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.execute_item_transfer_in_tx", fake_item_transfer_in_tx)
    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.check_item_possession_in_tx", fake_check_possession)

    reward_router = QuestRewardRouter(settings=_settings(), registry=_fake_registry())
    await reward_router.apply_rewards(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-4",
        player_id="player-1",
        meta=_meta(),
    )

    assert len(item_calls) == 1
    assert item_calls[0]["item_id"] == "item-bundle"
    assert item_calls[0]["quantity"] == 3


@pytest.mark.asyncio
async def test_apply_rewards_rejects_empty_reward_source(monkeypatch) -> None:
    # DEC-040: any non-empty string is now trusted; only "" is rejected.
    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return {
            "quest_id": quest_id,
            "player_id": player_id,
            "status": "completed",
            "title": "Delivery",
            "reward_source_id": "",
            "objectives": [{"objective_id": "obj-1", "target_count": 1}],
            "objective_progress": {"obj-1": 1},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }

    monkeypatch.setattr("npc_engine.engines.quest.quest_reward_router.get_quest_state", fake_get_quest_state)

    reward_router = QuestRewardRouter(settings=_settings(), registry=_fake_registry())
    with pytest.raises(QuestTransitionError) as error:
        await reward_router.apply_rewards(
            session=_fake_session(),  # type: ignore[arg-type]
            quest_id="quest-5",
            player_id="player-1",
            meta=_meta(),
        )

    assert error.value.code == "QUEST_REWARD_SOURCE_INVALID"
