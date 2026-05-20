"""
Module: story_pacing_engine
Layer: engines
Purpose: Meta-engine that reads active quests and recent events each tick, then writes
         max_event_severity and quest_generation_rate multipliers to WorldState so other
         engines can gate their sampling accordingly.
Does NOT: call LLMs, create graph nodes/edges, or expose HTTP routes.
Dependencies: engines.story_pacing.pacing_rules_loader, engines.story_pacing.pacing_queries,
              world.world_reader, world.world_writer
Dependencies injected: PacingRules (via constructor), AsyncSession (per tick call).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.story_pacing.pacing_queries import (
    CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS,
    CYPHER_GET_RECENT_MAJOR_EVENTS,
)
from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules
from npc_engine.world.world_reader import get_world_state
from npc_engine.world.world_writer import upsert_world_state

_LOGGER = logging.getLogger(__name__)


class StoryPacingEngine:
    """Gates high-severity events and new quest generation based on active quest state.

    On each tick:
    1. Queries active quests with severity >= high_severity_quest_threshold.
    2. Queries recent major events within the cooldown window.
    3. Computes new max_event_severity and quest_generation_rate.
    4. Writes updated values to WorldState.
    """

    def __init__(self, rules: PacingRules) -> None:
        """Initialise the engine with a loaded rule set.

        Args:
            rules: Validated PacingRules loaded from pacing_rules.yaml.
        """
        self._rules = rules
        self._lock = asyncio.Lock()

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict[str, Any]:
        """Execute one story pacing tick: evaluate suppression and update WorldState.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.

        Returns:
            Dict with max_event_severity (int), quest_generation_rate (float),
            and suppressed (bool).
        """
        async with self._lock:
            high_severity_quests = await self._get_active_high_severity_quests(session)
            recent_major_events = await self._get_recent_major_events(session, tick_id)

            suppressed = len(high_severity_quests) > 0
            relaxed_after_cooldown = len(recent_major_events) == 0 and not suppressed

            if suppressed:
                max_event_severity = self._rules.suppression_event_severity_cap
                quest_generation_rate = self._rules.suppression_quest_rate
            else:
                max_event_severity = 100
                quest_generation_rate = 1.0

            world_state = await get_world_state(session=session)
            updated = world_state.model_copy(
                update={
                    "max_event_severity": max_event_severity,
                    "quest_generation_rate": quest_generation_rate,
                }
            )
            await upsert_world_state(session=session, world_state=updated)

            _LOGGER.info(
                "story_pacing tick %d: suppressed=%s max_event_severity=%d quest_rate=%.2f",
                tick_id,
                suppressed,
                max_event_severity,
                quest_generation_rate,
            )
            return {
                "max_event_severity": max_event_severity,
                "quest_generation_rate": quest_generation_rate,
                "suppressed": suppressed,
                "relaxed_after_cooldown": relaxed_after_cooldown,
            }

    async def _get_active_high_severity_quests(
        self, session: AsyncSession
    ) -> list[dict[str, Any]]:
        """Query active quests with severity at or above the suppression threshold.

        Args:
            session: Active Neo4j async session.

        Returns:
            List of dicts with quest_id and severity keys.
        """
        result = await session.run(
            CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS,
            threshold=self._rules.high_severity_quest_threshold,
        )
        return [
            {"quest_id": r["quest_id"], "severity": int(r["severity"])}
            async for r in result
        ]

    async def _get_recent_major_events(
        self, session: AsyncSession, tick_id: int
    ) -> list[dict[str, Any]]:
        """Query major events that occurred within the cooldown window.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick; events at tick_id - cooldown_ticks or newer are checked.

        Returns:
            List of dicts with event_id, severity, and tick_id keys.
        """
        min_tick = max(0, tick_id - self._rules.cooldown_ticks)
        result = await session.run(
            CYPHER_GET_RECENT_MAJOR_EVENTS,
            min_tick_id=min_tick,
            floor=self._rules.major_event_severity_floor,
        )
        return [
            {
                "event_id": r["event_id"],
                "severity": int(r["severity"]),
                "tick_id": int(r["tick_id"]),
            }
            async for r in result
        ]
