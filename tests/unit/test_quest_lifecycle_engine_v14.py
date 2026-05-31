"""
test_quest_lifecycle_engine_v14.py - Unit tests for P3 quest lifecycle transitions.

Does NOT: execute real Neo4j writes.

Dependencies injected: monkeypatched quest persistence and reward coordinators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestObjectiveInput, QuestRewardCurrency, QuestRewardItem, QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.utils.errors import QuestTransitionError


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


@dataclass
class _FakeTx:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, tx: _FakeTx):
        self._tx = tx

    async def begin_transaction(self):
        return self._tx


def _fake_session() -> _FakeSession:
    return _FakeSession(tx=_FakeTx())


class _RollbackTx:
    def __init__(self, state_store: dict[tuple[str, str], dict[str, Any]]):
        self._state_store = state_store
        self.pending_state: dict[tuple[str, str], dict[str, Any]] = {}
        self.committed = False

    async def commit(self) -> None:
        self._state_store.update(self.pending_state)
        self.pending_state = {}
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _RollbackSession:
    def __init__(self, tx: _RollbackTx):
        self._tx = tx

    async def begin_transaction(self):
        return self._tx


@pytest.mark.asyncio
async def test_offer_accept_update_evaluate_and_apply_rewards_happy_path(monkeypatch) -> None:
    state_store: dict[tuple[str, str], dict] = {}

    async def fake_create_quest_state_if_absent(*, session, quest_id: str, player_id: str, state_payload: dict):
        key = (quest_id, player_id)
        if key not in state_store:
            state_store[key] = dict(state_payload)
        return dict(state_store[key])

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return state_store.get((quest_id, player_id))

    async def fake_upsert_quest_state(*, session, quest_id: str, player_id: str, state_payload: dict):
        state_store[(quest_id, player_id)] = dict(state_payload)
        return dict(state_payload)

    async def fake_event_write(*, tx, event):
        return None

    async def fake_item_transfer(**kwargs):
        return {"item_id": kwargs["item_id"], "quantity": kwargs["quantity"]}

    async def fake_currency_transfer(**kwargs):
        return {"amount": kwargs["amount"], "replayed": False}

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.create_quest_state_if_absent",
        fake_create_quest_state_if_absent,
    )
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_lifecycle_event", fake_event_write)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.apply_item_transfer", fake_item_transfer)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.apply_currency_transfer", fake_currency_transfer)

    async def fake_node_status_update(*, session, quest_id: str, status: str) -> None:
        pass

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.update_quest_node_status", fake_node_status_update)

    engine = QuestLifecycleEngine(settings=_settings())
    offered = await engine.offer_quest(
        session=_fake_session(),  # type: ignore[arg-type]
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
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-1",
        player_id="player-1",
        meta=_meta(),
    )
    assert accepted["status"] == "accepted"

    in_progress = await engine.update_objective(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-1",
        player_id="player-1",
        objective_id="obj-1",
        progress_delta=1,
        meta=_meta(),
    )
    assert in_progress["status"] == "in_progress"

    await engine.update_objective(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-1",
        player_id="player-1",
        objective_id="obj-1",
        progress_delta=1,
        meta=_meta(),
    )
    completed = await engine.evaluate_completion(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-1",
        player_id="player-1",
        meta=_meta(),
    )
    assert completed["status"] == "completed"

    reward_result = await engine.apply_rewards(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-1",
        player_id="player-1",
        meta=_meta(),
    )
    assert reward_result["status"] == "completed"
    assert reward_result["rewards_applied"] is True


@pytest.mark.asyncio
async def test_accept_requires_offered_state(monkeypatch) -> None:
    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        return None

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)

    engine = QuestLifecycleEngine(settings=_settings())
    with pytest.raises(QuestTransitionError):
        await engine.accept_quest(
            session=_fake_session(),  # type: ignore[arg-type]
            quest_id="quest-404",
            player_id="player-1",
            meta=_meta(),
        )


@pytest.mark.asyncio
async def test_offer_rejects_existing_offered_state_with_empty_reward_source(monkeypatch) -> None:
    # DEC-040: any non-empty string is now trusted; only "" is rejected.
    # Simulate a stored state whose reward_source_id was saved as "".
    async def fake_create_quest_state_if_absent(*, session, quest_id: str, player_id: str, state_payload: dict):
        return {
            "quest_id": quest_id,
            "player_id": player_id,
            "status": "offered",
            "reward_source_id": "",
            "title": "Collect herbs",
            "objectives": [{"objective_id": "obj-1", "target_count": 1}],
            "objective_progress": {"obj-1": 0},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.create_quest_state_if_absent",
        fake_create_quest_state_if_absent,
    )

    engine = QuestLifecycleEngine(settings=_settings())
    with pytest.raises(QuestTransitionError) as error:
        await engine.offer_quest(
            session=_fake_session(),  # type: ignore[arg-type]
            quest_id="quest-1",
            player_id="player-1",
            title="Collect herbs",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )

    assert error.value.code == "QUEST_REWARD_SOURCE_INVALID"


@pytest.mark.asyncio
async def test_apply_rewards_emits_provenance_event_with_transaction_support(monkeypatch) -> None:
    state_store: dict[tuple[str, str], dict[str, Any]] = {
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
    captured_event: dict[str, Any] = {}

    async def fake_get_quest_state(*, session, quest_id: str, player_id: str):
        payload = state_store.get((quest_id, player_id))
        return None if payload is None else dict(payload)

    async def fake_upsert_quest_state(*, session, quest_id: str, player_id: str, state_payload: dict):
        state_store[(quest_id, player_id)] = dict(state_payload)
        return dict(state_payload)

    async def fake_item_transfer(**kwargs):
        return {"request_id": kwargs["request_id"], "item_id": kwargs["item_id"]}

    async def fake_upsert_event(*, tx, event):
        captured_event["event"] = event

    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.apply_item_transfer", fake_item_transfer)
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_lifecycle_event", fake_upsert_event)

    tx = _FakeTx()
    session = _FakeSession(tx=tx)
    engine = QuestLifecycleEngine(settings=_settings())
    await engine.apply_rewards(
        session=session,  # type: ignore[arg-type]
        quest_id="quest-6",
        player_id="player-1",
        meta=_meta(),
    )

    assert tx.committed is True
    event = captured_event["event"]
    assert event.provenance["request_id"] == "req-quest-1"
    assert event.provenance["idempotency_key"] == "idem-quest-1"
    assert event.provenance["idempotency_request_hash"] == "hash-quest-1"


@pytest.mark.asyncio
async def test_offer_rolls_back_state_when_event_write_fails(monkeypatch) -> None:
    state_store: dict[tuple[str, str], dict[str, Any]] = {}

    async def fake_create_quest_state_if_absent(*, session, quest_id: str, player_id: str, state_payload: dict):
        session.pending_state[(quest_id, player_id)] = dict(state_payload)
        return dict(state_payload)

    async def failing_event_write(*, tx, event):
        raise RuntimeError("event write failure")

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.create_quest_state_if_absent",
        fake_create_quest_state_if_absent,
    )
    monkeypatch.setattr("npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_lifecycle_event", failing_event_write)

    tx = _RollbackTx(state_store=state_store)
    session = _RollbackSession(tx=tx)
    engine = QuestLifecycleEngine(settings=_settings())

    with pytest.raises(RuntimeError, match="event write failure"):
        await engine.offer_quest(
            session=session,  # type: ignore[arg-type]
            quest_id="quest-rollback-1",
            player_id="player-1",
            title="Deliver package",
            objectives=[QuestObjectiveInput(objective_id="obj-1", target_count=1)],
            item_rewards=[],
            currency_reward=None,
            meta=_meta(),
        )

    assert tx.committed is False
    assert state_store == {}
