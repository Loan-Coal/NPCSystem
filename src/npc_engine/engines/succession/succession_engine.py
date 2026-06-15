"""
Module: succession_engine
Layer: engines
Purpose: Per-tick succession scan for Phase 7.2 Political Simulation.
         Detects vacant inheritable titles and grants them to the first eligible heir
         in priority order. Does not handle non-inheritable titles.
Does NOT: call LLMs, create events, modify faction standings, open sessions, or
          import the graph layer.
Dependencies injected: PoliticalGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any, cast

from npc_engine.engines.ports.political_port import PoliticalGraphPort

_LOGGER = logging.getLogger(__name__)


class SuccessionEngine:
    """Detects vacant inheritable titles each tick and grants them to eligible heirs.

    Succession order: heirs are sorted by HEIR_OF.priority ascending (lower = first),
    then by HEIR_OF.legitimacy descending as a tiebreaker.

    A title is considered vacant when no Character has a HOLDS_TITLE edge to it.
    Only inheritable titles (is_inheritable=True) are processed.

    Graph access is injected as a PoliticalGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, political_repo: PoliticalGraphPort) -> None:
        """Initialise the succession engine.

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
        """Scan for vacant titles and apply succession at the given tick.

        Args:
            tick_id: Current game tick ID.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with key ``successions`` (count of titles granted).
        """
        vacant_titles = await self._political_repo.get_vacant_inheritable_titles()
        successions = 0
        for title in vacant_titles:
            if await self._grant_to_successor(title, tick_id=tick_id):
                successions += 1
        return {"successions": successions}

    async def _grant_to_successor(self, title: dict[str, Any], *, tick_id: int) -> bool:
        """Grant one vacant title to its first eligible heir, if any.

        Args:
            title: A vacant inheritable title row (needs ``id`` and ``faction_id``).
            tick_id: Current game tick, stamped onto the grant.

        Returns:
            True if the title was granted, else False (missing fields or no heir).
        """
        title_id = title.get("id")
        faction_id = title.get("faction_id")
        if not title_id or not faction_id:
            return False

        successor = await self._find_successor(faction_id=faction_id)
        if successor is None:
            _LOGGER.debug("succession: no eligible heir for title %s", title_id)
            return False

        await self._political_repo.grant_title(
            character_id=successor, title_id=title_id, tick=tick_id
        )
        _LOGGER.info(
            "succession: title %s (%s) granted to %s at tick %d",
            title_id,
            title.get("name", ""),
            successor,
            tick_id,
        )
        return True

    async def _find_successor(
        self,
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
            faction_id: ID used to look up heirs (treated as a character ID for now;
                        the political data model may expand this query later).

        Returns:
            Character ID of the first eligible heir, or None.
        """
        heirs = await self._political_repo.get_heirs_for_character(character_id=faction_id)
        if not heirs:
            return None
        return cast(str | None, heirs[0]["heir"].get("id"))
