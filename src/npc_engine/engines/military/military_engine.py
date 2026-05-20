"""
Module: military_engine
Layer: engines
Purpose: Stub military engine for Phase 7.4 Strategy/4X.
         Per-tick battle resolution, resource yield, and depletion logic
         are intentionally deferred — see ISSUES.md ISSUE-001.
         The engine is wired into TickScheduler so that future logic can be
         added without any scheduler-level changes.
Does NOT: call LLMs, write to graph, or perform any combat resolution.
Dependencies injected: None (stateless stub, no constructor args).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

_LOGGER = logging.getLogger(__name__)


class MilitaryEngine:
    """Stub engine — run_tick is a no-op placeholder.

    Per DECISIONS.md DEC-002: tick logic deferred until military mechanics
    are fully specced. The engine is wired and importable; expand run_tick
    when ready without touching TickScheduler.
    """

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """No-op tick — military logic not yet implemented.

        Args:
            session: Active Neo4j async session (unused by stub).
            tick_id: Current game tick ID.

        Returns:
            Dict indicating the tick was skipped.
        """
        _LOGGER.debug("military_engine tick=%d skipped (stub)", tick_id)
        return {"skipped": True, "reason": "military_logic_not_yet_implemented"}
