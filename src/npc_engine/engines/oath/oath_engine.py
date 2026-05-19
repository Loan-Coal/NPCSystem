"""
Module: oath_engine
Layer: engines
Purpose: Per-tick pledge lifecycle management — expires pledges past their expiry
         tick and runs stub violation checks against active pledges.
Does NOT: call LLMs, generate events, or implement pledge violation logic.
Dependencies injected: AsyncSession (via run_tick).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.pledge_service import (
    break_pledge,
    check_pledge_violations,
    get_expiring_pledges_svc,
)


class OathEngine:
    """Manages pledge expiry and stub violation checks on each tick."""

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Process pledge expiry and check for violations at the given tick.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with ``expired_pledges`` count.
        """
        expired = await get_expiring_pledges_svc(session, tick_id=tick_id)
        for pledge in expired:
            await break_pledge(
                session,
                pledger_id=pledge["pledger_id"],
                pledgee_id=pledge["pledgee_id"],
                pledge_type=pledge["pledge_type"],
                tick=tick_id,
            )

        # Stub: violation checks return [] — no action taken
        for pledge in expired:
            await check_pledge_violations(
                session,
                pledger_id=pledge["pledger_id"],
                tick=tick_id,
            )

        return {"expired_pledges": len(expired)}
