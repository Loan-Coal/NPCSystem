"""
Module: clique_formation_engine
Layer: engines
Purpose: Detects co-located character pairs with high mutual affection and forms clique groups.
         Runs every CLIQUE_FORMATION_TICK_INTERVAL ticks to avoid per-tick query overhead.
Does NOT: call LLMs, manage quest state, directly modify character attributes,
          open sessions, or import the graph layer.
Dependencies: engines.ports.group_port, config.Settings
Dependencies injected: Settings, GroupGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from npc_engine.config import Settings
from npc_engine.engines.ports.group_port import GroupGraphPort

_LOGGER = logging.getLogger(__name__)


class CliqueFormationEngine:
    """Detects high-affection co-located character pairs and auto-forms clique Groups.

    On each invocation (self-throttled by CLIQUE_FORMATION_TICK_INTERVAL):
    1. Queries pairs with bidirectional RELATES_TO.affection > 70 at the same location.
    2. Creates a clique Group for pairs not already sharing one.
    3. Dissolves cliques older than STALE_CLIQUE_AGE_TICKS.

    Graph access is injected as a GroupGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, settings: Settings, group_repo: GroupGraphPort) -> None:
        """Initialise the clique formation engine.

        Args:
            settings: Application settings providing the clique tick interval and
                affection/cohesion/stale-age thresholds.
            group_repo: Graph access port (group reads + writes).
        """
        self._interval = settings.CLIQUE_FORMATION_TICK_INTERVAL
        self._affection_threshold = settings.CLIQUE_AFFECTION_THRESHOLD
        self._initial_cohesion = settings.CLIQUE_INITIAL_COHESION
        self._stale_age_ticks = settings.CLIQUE_STALE_AGE_TICKS
        self._group_repo = group_repo
        self._lock = asyncio.Lock()

    async def run_tick(self, *, tick_id: int, **_: Any) -> dict[str, Any]:
        """Execute one clique formation pass if the tick interval is met.

        Args:
            tick_id: Current game tick identifier.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with keys ``formed`` (groups created), ``dissolved`` (groups dissolved),
            or ``skipped`` (True when the interval was not met).
        """
        if tick_id % self._interval != 0:
            return {"skipped": True}

        async with self._lock:
            return await self._run_formation(tick_id)

    async def _run_formation(self, tick_id: int) -> dict[str, Any]:
        """Inner formation pass — runs formation and decay logic.

        Args:
            tick_id: Current game tick.

        Returns:
            Dict with keys ``formed`` and ``dissolved``.
        """
        formed = 0
        dissolved = 0

        pairs: list[dict[str, Any]] = await self._group_repo.get_high_affection_pairs(
            threshold=self._affection_threshold
        )

        for pair in pairs:
            char_a = pair["char_a_id"]
            char_b = pair["char_b_id"]
            loc_a = pair.get("loc_a")
            loc_b = pair.get("loc_b")

            if loc_a is None or loc_a != loc_b:
                continue

            existing = await self._group_repo.get_existing_shared_group(
                char_a_id=char_a, char_b_id=char_b
            )
            if existing is not None:
                continue

            group_id = await self._group_repo.create_group(
                name=f"Clique ({char_a[:8]}, {char_b[:8]})",
                kind="clique",
                cohesion=self._initial_cohesion,
                is_secret=False,
                formed_at_tick=tick_id,
            )
            await self._group_repo.add_member(
                group_id=group_id,
                character_id=char_a,
                role="member",
                joined_at_tick=tick_id,
                commitment=50,
            )
            await self._group_repo.add_member(
                group_id=group_id,
                character_id=char_b,
                role="member",
                joined_at_tick=tick_id,
                commitment=50,
            )
            _LOGGER.info("clique: formed group %s for %s and %s", group_id, char_a, char_b)
            formed += 1

        stale_before = max(0, tick_id - self._stale_age_ticks)
        stale_groups: list[str] = await self._group_repo.get_stale_cliques(
            stale_before_tick=stale_before
        )
        for group_id in stale_groups:
            await self._group_repo.dissolve_group(group_id=group_id, tick=tick_id)
            _LOGGER.info("clique: dissolved stale group %s", group_id)
            dissolved += 1

        return {"formed": formed, "dissolved": dissolved}
