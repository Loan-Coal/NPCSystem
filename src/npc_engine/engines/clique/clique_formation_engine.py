"""
Module: clique_formation_engine
Layer: engines
Purpose: Detects co-located character pairs with high mutual affection and forms clique groups.
         Runs every CLIQUE_FORMATION_TICK_INTERVAL ticks to avoid per-tick query overhead.
Does NOT: call LLMs, manage quest state, or directly modify character attributes.
Dependencies: graph.group_queries, graph.group_service, config.Settings
Dependencies injected: AsyncSession (per tick call).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.group_queries import (
    CYPHER_GET_EXISTING_SHARED_GROUPS,
    CYPHER_GET_HIGH_AFFECTION_PAIRS,
    CYPHER_GET_STALE_CLIQUES,
)
from npc_engine.graph.group_service import (
    add_member,
    create_group,
    dissolve_group,
)

_LOGGER = logging.getLogger(__name__)

_AFFECTION_THRESHOLD = 70
_INITIAL_COHESION = 10
_STALE_CLIQUE_AGE_TICKS = 50


class CliqueFormationEngine:
    """Detects high-affection co-located character pairs and auto-forms clique Groups.

    On each invocation (self-throttled by CLIQUE_FORMATION_TICK_INTERVAL):
    1. Queries pairs with bidirectional RELATES_TO.affection > 70 at the same location.
    2. Creates a clique Group for pairs not already sharing one.
    3. Dissolves cliques older than STALE_CLIQUE_AGE_TICKS.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the clique formation engine.

        Args:
            settings: Application settings providing CLIQUE_FORMATION_TICK_INTERVAL.
        """
        self._interval = settings.CLIQUE_FORMATION_TICK_INTERVAL
        self._lock = asyncio.Lock()

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict[str, Any]:
        """Execute one clique formation pass if the tick interval is met.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.

        Returns:
            Dict with keys ``formed`` (groups created), ``dissolved`` (groups dissolved),
            or ``skipped`` (True when the interval was not met).
        """
        if tick_id % self._interval != 0:
            return {"skipped": True}

        async with self._lock:
            return await self._run_formation(session, tick_id)

    async def _run_formation(
        self, session: AsyncSession, tick_id: int
    ) -> dict[str, Any]:
        """Inner formation pass — runs formation and decay logic.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick.

        Returns:
            Dict with keys ``formed`` and ``dissolved``.
        """
        formed = 0
        dissolved = 0

        pairs_result = await session.run(
            CYPHER_GET_HIGH_AFFECTION_PAIRS, threshold=_AFFECTION_THRESHOLD
        )
        pairs: list[dict[str, Any]] = [dict(r) async for r in pairs_result]

        for pair in pairs:
            char_a = pair["char_a_id"]
            char_b = pair["char_b_id"]
            loc_a = pair.get("loc_a")
            loc_b = pair.get("loc_b")

            if loc_a is None or loc_a != loc_b:
                continue

            existing_result = await session.run(
                CYPHER_GET_EXISTING_SHARED_GROUPS,
                char_a_id=char_a,
                char_b_id=char_b,
            )
            existing = await existing_result.single()
            if existing is not None:
                continue

            group_id = await create_group(
                session,
                name=f"Clique ({char_a[:8]}, {char_b[:8]})",
                kind="clique",
                cohesion=_INITIAL_COHESION,
                is_secret=False,
                formed_at_tick=tick_id,
            )
            await add_member(
                session,
                group_id=group_id,
                character_id=char_a,
                role="member",
                joined_at_tick=tick_id,
                commitment=50,
            )
            await add_member(
                session,
                group_id=group_id,
                character_id=char_b,
                role="member",
                joined_at_tick=tick_id,
                commitment=50,
            )
            _LOGGER.info("clique: formed group %s for %s and %s", group_id, char_a, char_b)
            formed += 1

        stale_before = max(0, tick_id - _STALE_CLIQUE_AGE_TICKS)
        stale_result = await session.run(
            CYPHER_GET_STALE_CLIQUES, stale_before_tick=stale_before
        )
        stale_groups: list[str] = [r["group_id"] async for r in stale_result]
        for group_id in stale_groups:
            await dissolve_group(session, group_id=group_id, tick=tick_id)
            _LOGGER.info("clique: dissolved stale group %s", group_id)
            dissolved += 1

        return {"formed": formed, "dissolved": dissolved}
