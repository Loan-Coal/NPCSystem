"""
Module: player_model_port
Layer: engines
Purpose: Structural Protocol for the player-model write graph domain (upserting an NPC's
         perceived trust/intent of the player), so the player-model tick depends on one
         abstraction and holds no Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, derive perceived trust/intent, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/player_model/player_model_tick; implemented structurally by
         npc_engine.graph.repositories.player_model_repository.Neo4jPlayerModelRepository.
"""

from __future__ import annotations

from typing import Protocol


class PlayerModelGraphPort(Protocol):
    """Write access for upserting an NPC's model of the player (perceived trust/intent)."""

    async def upsert_player_model(
        self,
        *,
        npc_id: str,
        player_id: str,
        perceived_trust: int,
        perceived_intent: str,
        tick: int,
    ) -> None:
        """Upsert the PlayerModel node (idempotent MERGE on (npc_id, player_id))."""
        ...
