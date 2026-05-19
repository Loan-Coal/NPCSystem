"""
Module: need_decay_engine
Layer: engines
Purpose: Per-tick need decay for Phase 7.3 Social Simulation.
         Each tick, every character's need level drops by decay_rate.
         If the character is at a location with a SATISFIES_NEED edge,
         the magnitude is added back (net change may be positive or negative).
         Level is clamped to [0, 100] before writing.
Does NOT: call LLMs, create events, or modify faction/relationship state.
Dependencies injected: None (stateless, no constructor args).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.need_queries import get_all_needs_with_location
from npc_engine.graph.need_writer import set_need_level

_LOGGER = logging.getLogger(__name__)

_CRITICAL_THRESHOLD = 0


class NeedDecayEngine:
    """Applies per-tick need decay and location-based restoration for all characters.

    Algorithm (per need, per tick):
        new_level = clamp(level - decay_rate + satisfaction_magnitude, 0, 100)

    where satisfaction_magnitude comes from the SATISFIES_NEED.magnitude on the
    edge between the character's current LOCATED_AT location and the Need node.
    If the character has no location or no satisfier, satisfaction_magnitude = 0.
    """

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Decay all needs and apply location-based restoration.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with keys ``needs_updated`` (total updated) and
            ``needs_critical`` (count that hit level 0 this tick).
        """
        rows = await get_all_needs_with_location(session)

        needs_updated = 0
        needs_critical = 0

        for row in rows:
            need_id: str = row["need_id"]
            level: int = row["level"]
            decay_rate: int = row["decay_rate"]
            satisfaction_magnitude: int = row["satisfaction_magnitude"]

            new_level = level - decay_rate + satisfaction_magnitude
            new_level = max(0, min(100, new_level))

            if new_level == level:
                continue

            await set_need_level(session, need_id=need_id, level=new_level)
            needs_updated += 1

            if new_level == _CRITICAL_THRESHOLD:
                needs_critical += 1
                _LOGGER.warning(
                    "need: %s (char=%s kind=%s) reached critical level 0 at tick %d",
                    need_id,
                    row.get("character_id", "?"),
                    row.get("kind", "?"),
                    tick_id,
                )

        _LOGGER.debug(
            "need_decay tick=%d updated=%d critical=%d",
            tick_id,
            needs_updated,
            needs_critical,
        )
        return {"needs_updated": needs_updated, "needs_critical": needs_critical}
