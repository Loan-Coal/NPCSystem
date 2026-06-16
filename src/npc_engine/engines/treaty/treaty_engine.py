"""
Module: treaty_engine
Layer: engines
Purpose: Per-tick treaty lifecycle management — expires treaties and checks mechanical
         conditions for violations. Optional LLM evaluation is gated by TREATY_LLM_EVAL_ENABLED.
Does NOT: modify faction standings, generate events directly, open sessions, or
          import the graph layer.
Dependencies injected: TreatyGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

from typing import Any

from npc_engine.config import get_settings
from npc_engine.engines.ports.treaty_port import TreatyGraphPort


class TreatyEngine:
    """Manages treaty expiry and condition violation checks on each tick.

    Graph access is injected as a TreatyGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, treaty_repo: TreatyGraphPort) -> None:
        """Initialise the treaty engine.

        Args:
            treaty_repo: Graph access port for the treaty domain.
        """
        self._treaty_repo = treaty_repo

    async def run_tick(
        self,
        *,
        tick_id: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        """Process treaty expiry and condition checks at the given tick.

        Steps:
        1. Find active treaties past their expiry tick → expire them.
        2. For all remaining active treaties on known factions: check mechanical conditions.
        3. If TREATY_LLM_EVAL_ENABLED (default False): LLM eval would go here (not yet implemented).

        Args:
            tick_id: Current game tick ID.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with ``expired_treaties`` count and ``violations_detected`` count.
        """
        settings = get_settings()

        expiring_ids = await self._treaty_repo.get_expiring_treaties(tick_id=tick_id)
        for treaty_id in expiring_ids:
            await self._treaty_repo.expire_treaty(treaty_id=treaty_id, tick_id=tick_id)

        violations_detected = await self._count_active_violations(tick_id=tick_id)

        if settings.TREATY_LLM_EVAL_ENABLED:
            pass

        return {
            "expired_treaties": len(expiring_ids),
            "violations_detected": violations_detected,
        }

    async def _count_active_violations(self, *, tick_id: int) -> int:
        """Sum mechanically-violated conditions across all active treaties.

        Args:
            tick_id: Current game tick ID.

        Returns:
            Total number of violated conditions detected this tick.
        """
        active_treaty_ids = await self._treaty_repo.get_all_active_treaty_ids()
        total = 0
        for treaty_id in active_treaty_ids:
            violations = await self._treaty_repo.check_treaty_conditions_mechanical(
                treaty_id=treaty_id, tick_id=tick_id
            )
            total += len(violations)
        return total
