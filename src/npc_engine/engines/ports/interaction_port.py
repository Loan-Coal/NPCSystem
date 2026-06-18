"""
Module: interaction_port
Layer: engines
Purpose: Structural Protocol for the interaction graph domain — quest-state reads plus
         the objective-verification counters — so the interaction quest handlers and
         verifiers depend on one abstraction and hold no Neo4j session for their own
         reads (DEC-122 / SEV-24). Lifecycle writes stay on QuestLifecycleEngine.
Does NOT: open sessions, run Cypher, mutate quest state, call LLMs, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/interaction/quest_handler, engines/interaction/quest_verifier; implemented
         structurally by npc_engine.graph.repositories.interaction_repository.Neo4jInteractionRepository.
"""

from __future__ import annotations

from typing import Protocol, Any


class InteractionGraphPort(Protocol):
    """Read-only graph access for quest interaction proposals and objective verification."""

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict[str, Any] | None:
        """Return the QuestState snapshot for (quest_id, player_id), or None."""
        ...

    async def get_active_quest_for_player(self, *, player_id: str) -> dict[str, Any] | None:
        """Return the player's most recent accepted/in-progress quest state, or None."""
        ...

    async def count_player_has_item(self, *, player_id: str, item_id: str) -> int:
        """Return how many of item_id the player owns (OWNS edge quantity)."""
        ...

    async def count_player_located_at(self, *, player_id: str, location_id: str) -> int:
        """Return 1 if the player is currently LOCATED_AT the location, else 0."""
        ...

    async def count_player_was_at(self, *, player_id: str, location_id: str) -> int:
        """Return 1 if the player has a historical WAS_AT edge to the location, else 0."""
        ...

    async def count_target_inactive(self, *, target_id: str) -> int:
        """Return 1 if the target Character has is_active=False (death proxy), else 0."""
        ...

    async def count_player_co_located_with(self, *, player_id: str, target_id: str) -> int:
        """Return 1 if the player and target share a LOCATED_AT location, else 0."""
        ...
