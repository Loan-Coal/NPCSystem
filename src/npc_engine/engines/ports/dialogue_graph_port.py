"""
Module: dialogue_graph_port
Layer: engines
Purpose: Port Protocol for pure graph operations used by DialogueHandler.
Does NOT: import neo4j types; hold sessions; implement any graph logic.
Dependencies: engines.dialogue.dialogue_models, world.world_state
Used by: engines.dialogue.dialogue_handler, graph.repositories.dialogue_repository
Dependencies injected: None (Protocol only — concrete adapters are injected by the composition root)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
    from npc_engine.world.world_state import WorldState


class DialogueGraphPort(Protocol):
    """Abstraction over graph operations required by DialogueHandler per turn."""

    async def get_npc_archetype(self, npc_id: str) -> str | None:
        """Fetch the archetype string for an NPC node.

        Args:
            npc_id: NPC identifier.
        Returns:
            Archetype string, or None if not set.
        """
        ...

    async def get_npc_voice_descriptor(self, npc_id: str) -> str | None:
        """Fetch the voice_descriptor property for an NPC node.

        Args:
            npc_id: NPC identifier.
        Returns:
            Voice descriptor string, or None if not set.
        """
        ...

    async def get_world_state(self, world_id: str) -> WorldState | None:
        """Return the current WorldState for the given world node.

        Args:
            world_id: World node identifier.
        Returns:
            WorldState model, or None if the node is absent.
        """
        ...

    async def apply_relation_deltas(
        self,
        *,
        npc_id: str,
        player_id: str,
        relation_deltas: RelationDeltas,
        cause_id: str,
        tick_id: int,
        settings: object,
    ) -> None:
        """Apply relation deltas to the RELATES_TO edge; create it on first contact.

        Args:
            npc_id: Source NPC identifier.
            player_id: Destination player identifier.
            relation_deltas: Per-field deltas from the dialogue response.
            cause_id: Opaque cause string for audit logging.
            tick_id: Game tick for the log entry.
            settings: Application settings forwarded to the graph writer.
        Raises:
            GraphUnavailableError: If Neo4j is unreachable.
        """
        ...

    async def set_routine_override(
        self,
        *,
        character_id: str,
        location_id: str,
        expires_at_tick: int,
    ) -> None:
        """Override a character's routine destination until the expiry tick.

        Args:
            character_id: Character node identifier.
            location_id: Location identifier to override with.
            expires_at_tick: Tick at which the override expires.
        """
        ...
