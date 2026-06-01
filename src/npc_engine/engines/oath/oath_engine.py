"""
Module: oath_engine
Layer: engines
Purpose: Per-tick pledge lifecycle management — expires pledges past their expiry
         tick and detects active-pledge violations via WITNESSED/PARTICIPATED_IN edges.
Does NOT: call LLMs. Event emission is delegated to pledge_service.
Dependencies injected: AsyncSession (via run_tick).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.pledge_service import (
    break_pledge,
    get_all_active_pledgers_svc,
    get_expiring_pledges_svc,
)
from npc_engine.graph.pledge_violation_service import check_pledge_violations


class OathEngine:
    """Manages pledge expiry and violation checks on each tick."""

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Process pledge expiry and check all active pledges for violations.

        Expiry: break pledges that have reached their expires_at_tick.
        Violations: for each character with an active pledge, detect actions since
        sworn_at_tick that contradict the pledge semantics.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with ``expired_pledges`` and ``violated_pledges`` counts.
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

        all_pledgers = await get_all_active_pledgers_svc(session)
        total_violated = 0
        for pledger_id in all_pledgers:
            violations = await check_pledge_violations(
                session,
                pledger_id=pledger_id,
                tick=tick_id,
            )
            total_violated += len(violations)

        return {"expired_pledges": len(expired), "violated_pledges": total_violated}
