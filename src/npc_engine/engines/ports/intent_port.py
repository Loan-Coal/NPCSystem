"""
Module: intent_port
Layer: engines
Purpose: Structural Protocol for the proactive-dialogue intent graph domain (trigger reads
         + the PendingIntent queue writes) so the agenda intent engines depend on one
         abstraction and hold no Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, score intents, or import graph functions (only the
          ConversationIntent / Settings domain types passed through to the queue write).
Dependencies injected: none (pure interface).
Used by: engines/agenda/conversation_intent_service + engines/agenda/intent_formation_engine;
         implemented structurally by
         npc_engine.graph.repositories.intent_repository.Neo4jIntentRepository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from npc_engine.common.intent_models import ConversationIntent
    from npc_engine.config import Settings


class IntentGraphPort(Protocol):
    """Graph access for intent scoring (trigger reads) and the PendingIntent queue."""

    async def get_npc_location(self, *, npc_id: str) -> str | None:
        """Return the NPC's current location id, or None if unplaced."""
        ...

    async def get_player_location(self, *, player_id: str) -> str | None:
        """Return the player's current location id, or None if unplaced."""
        ...

    async def get_unmet_needs(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Return the NPC's unmet Need nodes."""
        ...

    async def get_witnessed_events(
        self, *, npc_id: str, since_tick: int
    ) -> list[dict[str, Any]]:
        """Return Event nodes the NPC learned about at or after since_tick."""
        ...

    async def get_unresolved_goals(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Return the NPC's Goal nodes whose status is not complete."""
        ...

    async def enqueue_intent(
        self, intent: ConversationIntent, *, settings: Settings
    ) -> None:
        """Enqueue a scored intent as a PendingIntent node (cap-enforced)."""
        ...

    async def expire_old_intents(self, *, cutoff_tick: int) -> int:
        """Mark pending intents created before cutoff_tick as expired; return the count."""
        ...
