"""
Module: oath_engine
Layer: engines
Purpose: Per-tick pledge lifecycle management — expires pledges past their expiry
         tick and detects active-pledge violations via WITNESSED/PARTICIPATED_IN edges.
Does NOT: call LLMs, open sessions, or import the graph layer. Event emission is
          delegated to the pledge graph adapter.
Dependencies injected: PledgeGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

from typing import Any

from npc_engine.engines.ports.pledge_port import PledgeGraphPort


class OathEngine:
    """Manages pledge expiry and violation checks on each tick.

    Graph access is injected as a PledgeGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, pledge_repo: PledgeGraphPort) -> None:
        """Initialise the oath engine.

        Args:
            pledge_repo: Graph access port for the pledge domain.
        """
        self._pledge_repo = pledge_repo

    async def run_tick(
        self,
        *,
        tick_id: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        """Process pledge expiry and check all active pledges for violations.

        Expiry: break pledges that have reached their expires_at_tick.
        Violations: for each character with an active pledge, detect actions since
        sworn_at_tick that contradict the pledge semantics.

        Args:
            tick_id: Current game tick ID.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with ``expired_pledges`` and ``violated_pledges`` counts.
        """
        expired = await self._pledge_repo.get_expiring_pledges(tick_id=tick_id)
        for pledge in expired:
            await self._pledge_repo.break_pledge(
                pledger_id=pledge["pledger_id"],
                pledgee_id=pledge["pledgee_id"],
                pledge_type=pledge["pledge_type"],
                tick=tick_id,
            )

        total_violated = await self._count_violations(tick_id=tick_id)
        return {"expired_pledges": len(expired), "violated_pledges": total_violated}

    async def _count_violations(self, *, tick_id: int) -> int:
        """Sum detected violations across all active pledgers.

        Args:
            tick_id: Current game tick ID.

        Returns:
            Total number of pledge violations detected this tick.
        """
        all_pledgers = await self._pledge_repo.get_all_active_pledgers()
        total = 0
        for pledger_id in all_pledgers:
            violations = await self._pledge_repo.check_pledge_violations(
                pledger_id=pledger_id, tick=tick_id
            )
            total += len(violations)
        return total
