"""
Module: player_location_read_port
Layer: engines
Purpose: Shared structural Protocol for player/NPC co-location reads (collocated pairs,
         player idle ticks), so engines that need location reads (player_model, director,
         proactive_dialogue) depend on one abstraction instead of holding a Neo4j session
         and calling PlayerLocationReader directly.
         Implemented in graph/repositories/player_location_read_repository.py.
Does NOT: open sessions, run Cypher, move NPCs, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: future player_model/director/proactive_dialogue slices; implemented structurally
         by npc_engine.graph.repositories.player_location_read_repository
         .Neo4jPlayerLocationReadRepository.
"""

from __future__ import annotations

from typing import Protocol


class PlayerLocationReadPort(Protocol):
    """Read-only access to player/NPC co-location state via LOCATED_AT edges."""

    async def get_collocated_pairs(self) -> list[tuple[str, str]]:
        """Return all (npc_id, player_id) pairs currently at the same location."""
        ...

    async def get_player_idle_ticks(
        self, *, npc_id: str, player_id: str, tick_id: int
    ) -> int:
        """Return how many ticks the player has been idle at the NPC's location (min 0)."""
        ...
