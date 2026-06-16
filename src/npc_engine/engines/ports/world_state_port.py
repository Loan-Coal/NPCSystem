"""
Module: world_state_port
Layer: engines
Purpose: Shared structural Protocol for the world-state graph domain (read the singleton
         WorldState, upsert it). Many engines need world state; they depend on this one
         Protocol instead of importing world_state_reader/world_state_writer and holding a
         Neo4j session. Implemented in graph/repositories/world_state_repository.py.
Does NOT: open sessions, run Cypher, derive pacing/multipliers, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.story_pacing.story_pacing_engine (and future world-state
         consumers); implemented structurally by
         npc_engine.graph.repositories.world_state_repository.Neo4jWorldStateRepository.
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.world.world_state import WorldState


class WorldStateGraphPort(Protocol):
    """Read/upsert the singleton WorldState node."""

    async def get_world_state(self, *, world_id: str = "world") -> WorldState:
        """Return the WorldState (or a default model when the node is absent)."""
        ...

    async def upsert_world_state(self, *, world_state: WorldState) -> WorldState:
        """Insert or update the singleton WorldState and return the confirmed model."""
        ...
