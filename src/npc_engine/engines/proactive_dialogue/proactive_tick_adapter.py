"""
Module: proactive_tick_adapter
Layer: engines
Purpose: Tick-scheduler adapter for ProactiveDialogueEngine.
         Calls get_collocated_pairs(), checks each pair against the engine,
         and emits proactive lines when triggers fire.
         Caps pair processing to MAX_PROACTIVE_CHECKS_PER_TICK per tick.
Does NOT: run Cypher directly; all graph queries are delegated to graph-layer readers.
Dependencies: engines.proactive_dialogue.proactive_engine.ProactiveDialogueEngine,
              graph.player_location_reader.PlayerLocationReader
Dependencies injected: ProactiveDialogueEngine, PlayerLocationReader (via __init__).
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py)
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.proactive_dialogue.proactive_engine import ProactiveDialogueEngine
from npc_engine.graph.player_location_reader import PlayerLocationReader

# Maximum (npc, player) pairs evaluated per scheduler tick.
# Prevents unbounded graph read cost when many NPCs share a location.
MAX_PROACTIVE_CHECKS_PER_TICK: int = 20

_logger = logging.getLogger(__name__)


class ProactiveDialogueTick:
    """Tick-scheduler adapter that wires ProactiveDialogueEngine into the clock loop.

    On each call to ``run_tick``:
    1. Fetches co-located (npc, player) pairs via PlayerLocationReader.
    2. Caps the list to MAX_PROACTIVE_CHECKS_PER_TICK.
    3. For each pair: calls engine.check_trigger(); if a trigger is returned,
       calls engine.generate_line() and collects the result.
    4. Returns {"proactive_lines": [<serialised lines>]}.

    No state is held beyond injected dependencies — safe for concurrent use.
    """

    def __init__(
        self,
        engine: ProactiveDialogueEngine,
        location_reader: PlayerLocationReader,
    ) -> None:
        """Initialise the adapter with injected dependencies.

        Args:
            engine: Configured ProactiveDialogueEngine instance.
            location_reader: PlayerLocationReader for co-location queries.
        """
        self._engine = engine
        self._location_reader = location_reader

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int,
    ) -> dict[str, Any]:
        """Run proactive dialogue checks for all co-located NPC/player pairs.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick.

        Returns:
            Dict with key ``proactive_lines``: list of serialised ProactiveLine dicts.
        """
        pairs = await self._location_reader.get_collocated_pairs(session)
        capped_pairs = pairs[:MAX_PROACTIVE_CHECKS_PER_TICK]

        if not capped_pairs:
            return {"proactive_lines": []}

        lines = []
        for npc_id, player_id in capped_pairs:
            line = await self._check_and_generate(
                session=session,
                npc_id=npc_id,
                player_id=player_id,
                tick_id=tick_id,
            )
            if line is not None:
                lines.append(line)

        _logger.info(
            "proactive_tick_done",
            extra={
                "tick_id": tick_id,
                "pairs_checked": len(capped_pairs),
                "lines_generated": len(lines),
            },
        )
        return {"proactive_lines": lines}

    async def _check_and_generate(
        self,
        *,
        session: AsyncSession,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> dict[str, Any] | None:
        """Check trigger and generate line for one NPC/player pair.

        Args:
            session: Active Neo4j async session.
            npc_id: NPC ID to check.
            player_id: Player ID to check.
            tick_id: Current game tick.

        Returns:
            Serialised ProactiveLine dict if triggered, else None.
        """
        trigger = await self._engine.check_trigger(
            session,
            npc_id=npc_id,
            player_id=player_id,
            tick_id=tick_id,
        )
        if trigger is None:
            return None
        line = await self._engine.generate_line(session, trigger)
        return line.model_dump()
