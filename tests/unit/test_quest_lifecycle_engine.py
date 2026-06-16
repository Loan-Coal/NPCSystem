"""
test_quest_lifecycle_engine.py - Unit tests for EXP-214 commitment memory formation on quest accept.

Covers:
- accept_quest triggers create_from_commitment when quest transitions offered → accepted.

Does NOT: connect to Neo4j. All graph calls and engine calls are mocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings
from npc_engine.engines.quest.models import QuestTransitionMeta
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.type_registry.contracts import TypeRegistry

_LIFECYCLE_MODULE = "npc_engine.engines.quest.quest_lifecycle_engine"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


@dataclass
class _FakeTx:
    """Fake transaction that records commit calls."""

    committed: bool = False

    async def commit(self) -> None:
        """Record commit."""
        self.committed = True

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeSession:
    """Fake session that returns a single _FakeTx."""

    def __init__(self, tx: _FakeTx) -> None:
        """Initialise with a transaction."""
        self._tx = tx

    async def begin_transaction(self) -> _FakeTx:
        """Return the fake transaction."""
        return self._tx


def _fake_session() -> _FakeSession:
    """Return a fresh _FakeSession."""
    return _FakeSession(tx=_FakeTx())


# ---------------------------------------------------------------------------
# EXP-214: commitment memory formed on quest accept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quest_accept_forms_commitment_memory(monkeypatch: Any) -> None:
    """Accepting an offered quest must call MemoryEngine.create_from_commitment.

    The memory engine call is patched at the class level so no DB writes occur.
    The test verifies that the call is made with kind='commitment' semantics
    by checking that create_from_commitment is invoked.
    """
    state_store: dict[tuple[str, str], dict[str, Any]] = {
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

    async def fake_get_quest_state(*, session: Any, quest_id: str, player_id: str) -> dict | None:
        return state_store.get((quest_id, player_id))

    async def fake_upsert_quest_state(
        *, session: Any, quest_id: str, player_id: str, state_payload: dict
    ) -> dict:
        state_store[(quest_id, player_id)] = dict(state_payload)
        return dict(state_payload)

    async def fake_event_write(*, tx: Any, event: Any) -> None:
        return None

    async def fake_node_status_update(*, session: Any, quest_id: str, status: str) -> None:
        return None

    async def fake_get_world_state(session: Any, world_id: str = "world") -> Any:
        from npc_engine.world.world_state import WorldState
        return WorldState(
            id="world",
            year=1,
            season="spring",
            day=1,
            time_of_day="morning",
        )

    monkeypatch.setattr(f"{_LIFECYCLE_MODULE}.get_quest_state", fake_get_quest_state)
    monkeypatch.setattr(f"{_LIFECYCLE_MODULE}.upsert_quest_state", fake_upsert_quest_state)
    monkeypatch.setattr(f"{_LIFECYCLE_MODULE}.upsert_quest_lifecycle_event", fake_event_write)
    monkeypatch.setattr(f"{_LIFECYCLE_MODULE}.update_quest_node_status", fake_node_status_update)
    monkeypatch.setattr(f"{_LIFECYCLE_MODULE}.get_world_state", fake_get_world_state)

    commitment_calls: list[dict[str, Any]] = []

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
    )
    stored = await engine.accept_quest(
        session=_fake_session(),  # type: ignore[arg-type]
        quest_id="quest-214",
        player_id="player_hero",
        meta=_meta(),
    )

    assert stored["status"] == "accepted"
    assert len(commitment_calls) == 1, (
        "accept_quest must call create_from_commitment exactly once on offered→accepted transition"
    )
    assert commitment_calls[0]["player_id"] == "player_hero"
