"""
Module: memory_consolidation_port
Layer: engines
Purpose: Structural Protocol for the graph operations MemoryConsolidationEngine needs
         (read beliefs/recent memories/undisclosed witnesses for context, write the
         consolidated Memory node), so the engine depends on an abstraction instead of
         importing graph query functions and holding a Neo4j session. Implemented in
         graph/repositories/memory_consolidation_repository.py.
Does NOT: open sessions, run Cypher, summarise turns, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.memory_consolidation.memory_consolidation_engine; implemented
         structurally by
         npc_engine.graph.repositories.memory_consolidation_repository.Neo4jMemoryConsolidationRepository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from npc_engine.world.time_utils import TimePoint


class MemoryConsolidationGraphPort(Protocol):
    """Graph reads (context enrichment) + the Memory write required by consolidation."""

    async def get_beliefs(self, *, character_id: str, k: int) -> list[dict[str, Any]]:
        """Return the character's top-k beliefs (confidence-ordered) for prompt context."""
        ...

    async def get_recent_memories(self, *, character_id: str, k: int) -> list[dict[str, Any]]:
        """Return the character's top-k recent memories (vividness-ordered) for prompt context."""
        ...

    async def get_undisclosed_witnesses(self, *, npc_id: str) -> list[dict[str, Any]]:
        """Return the NPC's undisclosed WITNESSED observations (latent rumor sources)."""
        ...

    async def create_memory(
        self,
        *,
        character_id: str,
        content: str,
        vividness: int,
        emotional_charge: int,
        game_time: TimePoint,
    ) -> str:
        """Persist a consolidated Memory node for the character; return its id."""
        ...
