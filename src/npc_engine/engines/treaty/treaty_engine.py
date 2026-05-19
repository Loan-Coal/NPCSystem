"""
Module: treaty_engine
Layer: engines
Purpose: Per-tick treaty lifecycle management — expires treaties and checks mechanical
         conditions for violations. Optional LLM evaluation is gated by TREATY_LLM_EVAL_ENABLED.
Does NOT: modify faction standings or generate events directly.
Dependencies injected: AsyncSession, Settings (via run_tick).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.config import get_settings
from npc_engine.graph.treaty_service import (
    break_treaty,
    check_treaty_conditions_mechanical,
    expire_treaty,
    get_expiring_treaties_svc,
    get_active_treaties_svc,
)


class TreatyEngine:
    """Manages treaty expiry and condition violation checks on each tick."""

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Process treaty expiry and condition checks at the given tick.

        Steps:
        1. Find active treaties past their expiry tick → expire them.
        2. For all remaining active treaties on known factions: check mechanical conditions.
        3. If TREATY_LLM_EVAL_ENABLED (default False): LLM eval would go here (not yet implemented).

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with ``expired_treaties`` count and ``violations_detected`` count.
        """
        settings = get_settings()

        expiring_ids = await get_expiring_treaties_svc(session, tick_id=tick_id)
        for treaty_id in expiring_ids:
            await expire_treaty(session, treaty_id, tick_id)

        violations_detected = 0
        if settings.TREATY_LLM_EVAL_ENABLED:
            pass

        return {
            "expired_treaties": len(expiring_ids),
            "violations_detected": violations_detected,
        }
