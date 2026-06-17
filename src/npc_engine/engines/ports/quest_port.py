"""
Module: quest_port
Layer: engines
Purpose: Structural Protocols for the quest graph domain — lifecycle state machine,
         offer flow, reward delivery, and chain resolution. Engines import these ports
         and hold no Neo4j session; the adapter (graph/repositories/quest_repository.py)
         owns session-per-call and atomic run_in_tx operations.
Does NOT: open sessions, run Cypher, or contain engine logic.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.quest.* (all quest engine classes).
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.config import Settings
from npc_engine.world.world_state import WorldState


class QuestLifecycleGraphPort(Protocol):
    """Read quest state, atomically persist state+event, and update node status."""

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict | None:
        """Return the persisted QuestState dict or None if absent."""
        ...

    async def persist_state_and_event(
        self,
        *,
        quest_id: str,
        player_id: str,
        state_payload: dict,
        event_node: dict,
    ) -> dict:
        """Atomically upsert quest state and emit a lifecycle event; return stored state."""
        ...

    async def emit_lifecycle_event(self, *, event_node: dict) -> None:
        """Atomically write one quest lifecycle event node."""
        ...

    async def update_quest_node_status(self, *, quest_id: str, status: str) -> None:
        """Update the Quest node's status field (non-atomic, called after persist)."""
        ...

    async def get_world_state(self, *, world_id: str = "world") -> WorldState:
        """Return the singleton WorldState (used for commitment-memory TimePoint)."""
        ...


class QuestOfferGraphPort(Protocol):
    """Quest node reads, status updates, and atomic offer creation."""

    async def get_quest(self, *, quest_id: str) -> dict | None:
        """Return the Quest node dict or None."""
        ...

    async def update_quest_node_status(self, *, quest_id: str, status: str) -> None:
        """Update the Quest node's status field."""
        ...

    async def offer_quest_atomic(
        self,
        *,
        quest_id: str,
        player_id: str,
        state_payload: dict,
        event_node: dict,
    ) -> dict:
        """Atomically create-if-absent QuestState and emit offered event; return stored state."""
        ...


class QuestRewardGraphPort(Protocol):
    """Quest state reads, balance check, and atomic reward application."""

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict | None:
        """Return the persisted QuestState dict or None if absent."""
        ...

    async def get_character_balance(self, *, character_id: str) -> int | None:
        """Return the character's current currency balance, or None if not found."""
        ...

    async def emit_lifecycle_event(self, *, event_node: dict) -> None:
        """Atomically write one quest lifecycle event node (idempotent path)."""
        ...

    async def apply_rewards_atomic(
        self,
        *,
        quest_id: str,
        player_id: str,
        request_id: str,
        state_dict: dict,
        next_state_payload: dict,
        event_node: dict,
        settings: Settings,
    ) -> dict:
        """Atomically collect delivery items, grant rewards, persist state+event; return stored.

        request_id: from QuestTransitionMeta.request_id — used for idempotency keys.
        state_dict: serialized QuestStateRecord (model_dump); adapter uses reward_source_id,
            item_rewards, currency_reward, and objectives from it.
        """
        ...


class QuestChainGraphPort(Protocol):
    """Quest chain reads — UNLOCKS edges and Quest node lookup for chain resolution."""

    async def get_quest(self, *, quest_id: str) -> dict | None:
        """Return the Quest node dict or None."""
        ...

    async def get_unlocked_quests(self, *, quest_id: str, outcome: str) -> list[str]:
        """Return IDs of quests unlocked by quest_id at the given outcome."""
        ...

    async def get_choice_unlocked_quest(
        self, *, quest_id: str, choice_id: str
    ) -> str | None:
        """Return the quest ID unlocked by a specific player choice, or None."""
        ...
