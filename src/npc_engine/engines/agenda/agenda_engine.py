"""
Module: agenda_engine
Layer: engines
Purpose: Per-tick agenda resolution for Phase 7.2 Political Simulation.
         Tallies SUPPORTS_AGENDA and OPPOSES_AGENDA weights for agendas past
         their deadline and marks them passed or failed.
Does NOT: call LLMs, create events, or modify faction standings.
Dependencies injected: None (stateless, no constructor args).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.political_queries import get_agenda_votes, get_expired_open_agendas
from npc_engine.graph.political_writer import set_agenda_status

_LOGGER = logging.getLogger(__name__)


class AgendaEngine:
    """Resolves open agendas whose deadline has passed each tick.

    Resolution logic:
    - Sum SUPPORTS_AGENDA.weight across all supporters.
    - Sum OPPOSES_AGENDA.weight across all opposers.
    - If total support > total opposition → status = 'passed'.
    - If total opposition >= total support → status = 'failed'.
    - Agendas with no votes are marked 'failed' (no consensus = failure).
    """

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Resolve all open agendas whose deadline_tick <= tick_id.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with keys ``resolved`` (total count), ``passed`` (count),
            and ``failed`` (count).
        """
        expired = await get_expired_open_agendas(session, current_tick=tick_id)
        resolved = 0
        passed = 0
        failed = 0

        for agenda in expired:
            agenda_id = agenda.get("id")
            if not agenda_id:
                continue

            votes = await get_agenda_votes(session, agenda_id=agenda_id)
            support_total = sum(v.get("weight", 0) for v in votes["supports"])
            oppose_total = sum(v.get("weight", 0) for v in votes["opposes"])

            outcome = "passed" if support_total > oppose_total else "failed"
            await set_agenda_status(session, agenda_id=agenda_id, status=outcome)

            if outcome == "passed":
                passed += 1
            else:
                failed += 1
            resolved += 1

            _LOGGER.info(
                "agenda: %s (%s) resolved at tick %d — support=%d oppose=%d → %s",
                agenda_id,
                agenda.get("description", "")[:40],
                tick_id,
                support_total,
                oppose_total,
                outcome,
            )

        return {"resolved": resolved, "passed": passed, "failed": failed}
