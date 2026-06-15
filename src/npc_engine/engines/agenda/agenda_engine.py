"""
Module: agenda_engine
Layer: engines
Purpose: Per-tick agenda resolution for Phase 7.2 Political Simulation.
         Tallies SUPPORTS_AGENDA and OPPOSES_AGENDA weights for agendas past
         their deadline and marks them passed or failed.
Does NOT: call LLMs, create events, modify faction standings, open sessions, or
          import the graph layer.
Dependencies injected: PoliticalGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from npc_engine.engines.ports.political_port import PoliticalGraphPort

_LOGGER = logging.getLogger(__name__)


class AgendaEngine:
    """Resolves open agendas whose deadline has passed each tick.

    Resolution logic:
    - Sum SUPPORTS_AGENDA.weight across all supporters.
    - Sum OPPOSES_AGENDA.weight across all opposers.
    - If total support > total opposition → status = 'passed'.
    - If total opposition >= total support → status = 'failed'.
    - Agendas with no votes are marked 'failed' (no consensus = failure).

    Graph access is injected as a PoliticalGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, political_repo: PoliticalGraphPort) -> None:
        """Initialise the agenda engine.

        Args:
            political_repo: Graph access port for the political domain.
        """
        self._political_repo = political_repo

    async def run_tick(
        self,
        *,
        tick_id: int = 0,
        **_: Any,
    ) -> dict[str, Any]:
        """Resolve all open agendas whose deadline_tick <= tick_id.

        Args:
            tick_id: Current game tick ID.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with keys ``resolved`` (total count), ``passed`` (count),
            and ``failed`` (count).
        """
        expired = await self._political_repo.get_expired_open_agendas(current_tick=tick_id)
        resolved = 0
        passed = 0
        failed = 0

        for agenda in expired:
            agenda_id = agenda.get("id")
            if not agenda_id:
                continue

            votes = await self._political_repo.get_agenda_votes(agenda_id=agenda_id)
            support_total = sum(v.get("weight", 0) for v in votes["supports"])
            oppose_total = sum(v.get("weight", 0) for v in votes["opposes"])

            outcome = "passed" if support_total > oppose_total else "failed"
            await self._political_repo.set_agenda_status(agenda_id=agenda_id, status=outcome)

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
