"""
Module: need_decay_engine
Layer: engines
Purpose: Per-tick need decay for Phase 7.3 Social Simulation.
         Each tick, every character's need level drops by decay_rate.
         If the character is at a location with a SATISFIES_NEED edge,
         the magnitude is added back (net change may be positive or negative).
         Level is clamped to [0, 100] before writing.
Does NOT: call LLMs, create events, modify faction/relationship state, open
          sessions, or import the graph layer.
Dependencies injected: NeedGraphPort (graph access) via __init__.
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from npc_engine.engines.ports.need_port import NeedGraphPort

_LOGGER = logging.getLogger(__name__)

_CRITICAL_THRESHOLD = 0


class NeedDecayEngine:
    """Applies per-tick need decay and location-based restoration for all characters.

    Algorithm (per need, per tick):
        new_level = clamp(level - decay_rate + satisfaction_magnitude, 0, 100)

    where satisfaction_magnitude comes from the SATISFIES_NEED.magnitude on the
    edge between the character's current LOCATED_AT location and the Need node.
    If the character has no location or no satisfier, satisfaction_magnitude = 0.

    Graph access is injected as a NeedGraphPort (DEC-122 / SEV-24), so the engine
    holds no Neo4j session; the tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, need_repo: NeedGraphPort) -> None:
        """Initialise with the injected graph port.

        Args:
            need_repo: Graph access port (read needs, write levels).
        """
        self._need_repo = need_repo

    async def run_tick(
        self,
        *,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Decay all needs and apply location-based restoration.

        Args:
            tick_id: Current game tick ID.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with keys ``needs_updated`` (total updated) and
            ``needs_critical`` (count that hit level 0 this tick).
        """
        rows = await self._need_repo.get_all_needs_with_location()

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

            await self._need_repo.set_need_level(need_id=need_id, level=new_level)
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
