"""
Module: succession_engine
Layer: engines
Purpose: Per-tick succession scan for Phase 7.2 Political Simulation.
         Detects vacant inheritable titles and grants them to the first eligible heir
         in priority order. Does not handle non-inheritable titles.
Does NOT: call LLMs, create events, or modify faction standings.
Dependencies injected: None (stateless, no constructor args).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.political_queries import (
    get_heirs_for_character,
    get_vacant_inheritable_titles,
)
from npc_engine.graph.political_writer import grant_title

_LOGGER = logging.getLogger(__name__)


class SuccessionEngine:
    """Detects vacant inheritable titles each tick and grants them to eligible heirs.

    Succession order: heirs are sorted by HEIR_OF.priority ascending (lower = first),
    then by HEIR_OF.legitimacy descending as a tiebreaker.

    A title is considered vacant when no Character has a HOLDS_TITLE edge to it.
    Only inheritable titles (is_inheritable=True) are processed.
    """

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int = 0,
    ) -> dict[str, Any]:
        """Scan for vacant titles and apply succession at the given tick.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick ID.

        Returns:
            Dict with key ``successions`` (count of titles granted).
        """
        vacant_titles = await get_vacant_inheritable_titles(session)
        successions = 0

        for title in vacant_titles:
            title_id = title.get("id")
            faction_id = title.get("faction_id")
            if not title_id or not faction_id:
                continue

            successor = await self._find_successor(session, faction_id=faction_id)
            if successor is None:
                _LOGGER.debug("succession: no eligible heir for title %s", title_id)
                continue

            await grant_title(session, character_id=successor, title_id=title_id, tick=tick_id)
            _LOGGER.info(
                "succession: title %s (%s) granted to %s at tick %d",
                title_id,
                title.get("name", ""),
                successor,
                tick_id,
            )
            successions += 1

        return {"successions": successions}

    async def _find_successor(
        self,
        session: AsyncSession,
        *,
        faction_id: str,
    ) -> str | None:
        """Find the highest-priority heir among characters in the faction.

        Queries all characters who hold HEIR_OF edges to any character in the faction.
        Returns the heir's character ID, or None if no heirs exist.

        For simplicity this implementation queries heirs of the faction itself if
        faction_id can be treated as a character reference, or returns None. In a
        richer schema this would traverse faction membership to find the most senior
        member's heir chain. Current implementation requires callers to use
        ``get_heirs_for_character`` directly if they know the predecessor's ID.

        Args:
            session: Active Neo4j async session.
            faction_id: ID used to look up heirs (treated as a character ID for now;
                        the political data model may expand this query later).

        Returns:
            Character ID of the first eligible heir, or None.
        """
        heirs = await get_heirs_for_character(session, character_id=faction_id)
        if not heirs:
            return None
        return heirs[0]["heir"].get("id")
