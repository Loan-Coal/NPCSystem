"""
Module: memory_engine
Layer: engines
Purpose: Rules-based engine for forming memories from high-arousal moments and running daily vividness decay.
Does NOT: query or persist state directly — all I/O is delegated to graph.memory_service.
Dependencies: graph.memory_service, world.time_utils
Dependencies injected: AsyncSession (per method call).
Used by: engines.dialogue.dialogue_handler, api.routes.clock
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.memory_service import (
    create_memory,
    decay_all_vividness,
    decay_all_vividness_weighted,
)
from npc_engine.world.time_utils import TimePoint

_HIGH_AROUSAL_THRESHOLD = 70
_HIGH_AROUSAL_VIVIDNESS = 80
_DECAY_BASE_RATE = 5
_DECAY_CHARGE_DIVISOR = 20


class MemoryEngine:
    """Rules-based engine for memory formation and vividness decay.

    Memory formation triggers when NPC arousal exceeds the high-arousal
    threshold after a dialogue exchange. Vividness decay runs once per
    day advance, reducing all memory vividness by a fixed amount.
    """

    async def create_from_arousal(
        self,
        session: AsyncSession,
        *,
        character_id: str,
        arousal: int,
        content: str,
        game_time: TimePoint,
    ) -> str | None:
        """Create a memory if arousal exceeds the high-arousal threshold.

        Args:
            session: Active Neo4j async session.
            character_id: ID of the NPC who formed the memory.
            arousal: Current arousal level (0–100).
            content: Description of the memorable moment.
            game_time: Game-time snapshot at moment of formation.

        Returns:
            Memory ID string if a memory was created, else None.
        """
        if arousal <= _HIGH_AROUSAL_THRESHOLD:
            return None
        return await create_memory(
            session,
            character_id=character_id,
            content=content,
            vividness=_HIGH_AROUSAL_VIVIDNESS,
            emotional_charge=min(100, arousal - 50),
            game_time=game_time,
        )

    async def decay_vividness(self, session: AsyncSession) -> int:
        """Reduce all memory vividness by the default daily decay amount.

        Args:
            session: Active Neo4j async session.

        Returns:
            Number of Memory nodes updated.
        """
        return await decay_all_vividness(session)

    async def decay_vividness_weighted(self, session: AsyncSession) -> int:
        """Reduce memory vividness using a charge-weighted rate.

        High emotional_charge memories decay slower; trivial memories decay faster.
        Uses _DECAY_BASE_RATE and _DECAY_CHARGE_DIVISOR module constants.

        Args:
            session: Active Neo4j async session.

        Returns:
            Number of Memory nodes whose vividness was reduced.
        """
        return await decay_all_vividness_weighted(
            session,
            base_decay=_DECAY_BASE_RATE,
            charge_divisor=_DECAY_CHARGE_DIVISOR,
        )
