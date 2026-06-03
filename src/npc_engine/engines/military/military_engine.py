"""
Module: military_engine
Layer: engines
Purpose: Per-tick military simulation — resolves battles between opposing armies and
         processes resource yield for controlling factions.
Does NOT: call LLMs or perform graph writes directly (delegated to services).
Dependencies injected: AsyncSession (via run_tick).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.military.military_battle_service import resolve_battles
from npc_engine.engines.military.military_resource_service import process_resource_yield

_LOGGER = logging.getLogger(__name__)


class MilitaryEngine:
    """Runs battle resolution and resource yield on every tick."""

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Resolve all active battles and process resource yield.

        Steps:
        1. Detect locations with opposing armies → resolve each battle (strength
           comparison, damage, CONTROLS/OCCUPIES updates, battle Event node).
        2. For each faction controlling a producing location with depletion > 0:
           credit treasury and decrement ResourceNode.depletion.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with ``battles_resolved`` count and ``factions_yielded`` count.
        """
        battles = await resolve_battles(session, tick_id=tick_id)
        yields = await process_resource_yield(session, tick_id=tick_id)

        _LOGGER.info(
            "military_tick_complete",
            extra={
                "tick": tick_id,
                "battles_resolved": len(battles),
                "factions_yielded": len(yields),
            },
        )

        return {
            "battles_resolved": len(battles),
            "factions_yielded": len(yields),
        }
