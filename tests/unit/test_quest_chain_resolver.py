"""
Module: test_quest_chain_resolver
Layer: tests (unit)
Purpose: Unit tests for QuestChainResolver — verifies chain resolution, no-op on empty
    chain, outcome propagation, and lifecycle engine integration.
Dependencies: npc_engine.engines.quest.quest_chain_resolver,
    npc_engine.engines.quest.quest_lifecycle_engine,
    npc_engine.engines.quest.models, unittest.mock
Used by: pytest (make test)

Does NOT: touch Neo4j, call the LLM, or exercise real graph queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import (
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.type_registry.contracts import TypeRegistry


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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


class _FakeSession:
    """Minimal async session stub."""


@dataclass
class _FakeTx:
    committed: bool = False

    async def commit(self) -> None:
        self.committed = True

    async def run(self, query: str, **kwargs: Any) -> Any:
        result = MagicMock()
        result.single = AsyncMock(return_value=None)
        result.consume = AsyncMock()
        return result

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeSessionWithTx(_FakeSession):
    def __init__(self) -> None:
        self._tx = _FakeTx()

    async def begin_transaction(self) -> _FakeTx:
        return self._tx

    async def run(self, query: str, **kwargs: Any) -> Any:
        result = MagicMock()
        result.single = AsyncMock(return_value=None)
        result.consume = AsyncMock()
        return result


# ---------------------------------------------------------------------------
# Test 1 — happy path: UNLOCKS edge found → offer_quest called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_offers_next_quest_on_complete(monkeypatch: Any) -> None:
    """When get_unlocked_quests returns one next quest, offer_quest is called for it."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    resolver = QuestChainResolver(offer_service=offer_service)
    session = _FakeSession()

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_chain_resolver.get_unlocked_quests",
        AsyncMock(return_value=["quest_b"]),
    )

    await resolver.resolve(
        session=session,  # type: ignore[arg-type]
        quest_id="quest_a",
        player_id="player_demo",
        outcome="complete",
    )

    offer_service.offer_quest.assert_awaited_once_with(
        session=session,
        next_quest_id="quest_b",
        player_id="player_demo",
    )


# ---------------------------------------------------------------------------
# Test 2 — no chain: empty list → offer_quest NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_no_op_when_no_chain(monkeypatch: Any) -> None:
    """When get_unlocked_quests returns empty list, offer_quest is not called."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    resolver = QuestChainResolver(offer_service=offer_service)
    session = _FakeSession()

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_chain_resolver.get_unlocked_quests",
        AsyncMock(return_value=[]),
    )

    await resolver.resolve(
        session=session,  # type: ignore[arg-type]
        quest_id="quest_a",
        player_id="player_demo",
        outcome="complete",
    )

    offer_service.offer_quest.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 3 — fail outcome: correct on_outcome passed to get_unlocked_quests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_passes_fail_outcome(monkeypatch: Any) -> None:
    """resolver.resolve(..., outcome='fail') passes outcome='fail' to get_unlocked_quests."""
    offer_service = MagicMock()
    offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    resolver = QuestChainResolver(offer_service=offer_service)
    session = _FakeSession()

    mock_get = AsyncMock(return_value=["quest_c"])
    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_chain_resolver.get_unlocked_quests",
        mock_get,
    )

    await resolver.resolve(
        session=session,  # type: ignore[arg-type]
        quest_id="quest_a",
        player_id="player_demo",
        outcome="fail",
    )

    mock_get.assert_awaited_once_with(
        session=session,
        quest_id="quest_a",
        outcome="fail",
    )


# ---------------------------------------------------------------------------
# Test 4 — lifecycle engine calls resolver on COMPLETED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifecycle_engine_calls_resolver_on_completion(monkeypatch: Any) -> None:
    """QuestLifecycleEngine with chain_resolver calls resolver.resolve after COMPLETED transition."""
    completed_state = {
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

    async def fake_get_quest_state(*, session: Any, quest_id: str, player_id: str) -> dict | None:
        return dict(completed_state)

    async def fake_upsert_quest_state(
        *, session: Any, quest_id: str, player_id: str, state_payload: dict
    ) -> dict:
        return dict(state_payload)

    async def fake_upsert_lifecycle_event(*, tx: Any, event: Any) -> None:
        return None

    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.get_quest_state",
        fake_get_quest_state,
    )
    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_state",
        fake_upsert_quest_state,
    )
    monkeypatch.setattr(
        "npc_engine.engines.quest.quest_lifecycle_engine.upsert_quest_lifecycle_event",
        fake_upsert_lifecycle_event,
    )

    mock_resolver = MagicMock()
    mock_resolver.resolve = AsyncMock(return_value=None)

    engine = QuestLifecycleEngine(
        settings=_settings(),
        registry=_fake_registry(),
        chain_resolver=mock_resolver,
    )
    session = _FakeSessionWithTx()

    await engine.evaluate_completion(
        session=session,  # type: ignore[arg-type]
        quest_id="quest_a",
        player_id="player_demo",
        meta=_meta(),
    )

    mock_resolver.resolve.assert_awaited_once_with(
        session=session,
        quest_id="quest_a",
        player_id="player_demo",
        outcome="complete",
    )
