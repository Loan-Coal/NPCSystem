"""
Module: memory_port
Layer: engines
Purpose: Structural Protocol for creating Memory nodes and running vividness decay, so
         MemoryEngine depends on one abstraction and holds no Neo4j session for its
         writes (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, decide memory thresholds, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/memory/memory_engine; implemented structurally by
         npc_engine.graph.repositories.memory_repository.Neo4jMemoryRepository.
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.world.time_utils import TimePoint


class MemoryGraphPort(Protocol):
    """Persistence access for Memory nodes and their vividness decay."""

    async def create_memory(
        self,
        *,
        character_id: str,
        content: str,
        vividness: int,
        emotional_charge: int,
        game_time: TimePoint,
        subject_player_id: str | None = None,
        kind: str | None = None,
    ) -> str:
        """Create a Memory node for a character and return its node id."""
        ...

    async def decay_all_vividness(self) -> int:
        """Reduce every Memory node's vividness by the default daily amount."""
        ...

    async def decay_all_vividness_weighted(
        self,
        *,
        base_decay: int,
        charge_divisor: int,
    ) -> int:
        """Reduce vividness with a charge-weighted rate; return nodes affected."""
        ...
