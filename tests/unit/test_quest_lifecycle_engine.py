"""
test_quest_lifecycle_engine.py - Unit tests for EXP-214 commitment memory formation on quest accept.

Covers:
- accept_quest triggers create_from_commitment when quest transitions offered → accepted.

Does NOT: connect to Neo4j. All graph calls go through a mock QuestLifecycleGraphPort.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.type_registry.contracts import TypeRegistry


class _FakeEventModel(BaseModel):
    """Minimal fake event model to satisfy TypeRegistry construction."""

    model_config = ConfigDict(extra="allow")
    id: str = ""
    summary: str = ""
    provenance: dict = {}


def _fake_registry() -> TypeRegistry:
    """Return a minimal TypeRegistry usable in tests."""
    return TypeRegistry(schema_version="1.0", node_models={"event": _FakeEventModel})


def _settings() -> Settings:
    """Return a Settings instance with a dummy API key."""
    return Settings(API_KEY_SECRET="local_dev_secret_change_this_2026")


def _meta() -> QuestTransitionMeta:
    """Return a standard transition meta for tests."""
    return QuestTransitionMeta(
        request_id="req-214-1",
        actor_id="player_hero",
        reason="story_progression",
        idempotency_key="idem-214-1",
        idempotency_request_hash="hash-214-1",
    )


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


@pytest.mark.asyncio
async def test_quest_accept_forms_commitment_memory() -> None:
    """Accepting an offered quest must call MemoryEngine.create_from_commitment.

    The memory engine is injected — no DB writes occur. The test verifies
    create_from_commitment is invoked once with kind='commitment' semantics.
    """
    state_store: dict = {
        ("quest-214", "player_hero"): {
            "quest_id": "quest-214",
            "player_id": "player_hero",
            "status": "offered",
            "reward_source_id": "system",
            "title": "Retrieve the lost seal",
            "objectives": [],
            "objective_progress": {},
            "item_rewards": [],
            "currency_reward": None,
            "rewards_applied": False,
        }
    }

    commitment_calls: list[dict] = []

    class _FakeMemoryEngine:
        async def create_from_commitment(
            self,
            *,
            character_id: str,
            content: str,
            game_time: Any,
            player_id: str | None = None,
        ) -> str:
            commitment_calls.append(
                {"character_id": character_id, "content": content, "player_id": player_id}
            )
            return "mem-commitment-001"

    engine = QuestLifecycleEngine(
        settings=_settings(),
        registry=_fake_registry(),
        memory_engine=_FakeMemoryEngine(),  # type: ignore[arg-type]
        quest_repo=_make_lifecycle_repo(state_store),
    )
    stored = await engine.accept_quest(
        quest_id="quest-214",
        player_id="player_hero",
        meta=_meta(),
    )

    assert stored["status"] == "accepted"
    assert len(commitment_calls) == 1, (
        "accept_quest must call create_from_commitment exactly once on offered→accepted transition"
    )
    assert commitment_calls[0]["player_id"] == "player_hero"
