"""
Module: character_read_port
Layer: engines
Purpose: Shared structural Protocol for reading the active NPC roster, so engines that
         need the full character list (reputation, planning) depend on one abstraction
         instead of importing character_reader and holding a Neo4j session.
         Implemented in graph/repositories/character_read_repository.py.
Does NOT: open sessions, run Cypher, derive models, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: future reputation/planning slices; implemented structurally by
         npc_engine.graph.repositories.character_read_repository.Neo4jCharacterReadRepository.
"""

from __future__ import annotations

from typing import Protocol


class CharacterReadPort(Protocol):
    """Read-only access to the active non-player Character roster."""

    async def get_npc_ids(self) -> list[str]:
        """Return the IDs of all active non-player Characters (empty list if none)."""
        ...
