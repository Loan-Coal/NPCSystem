"""
Module: story_pacing_engine
Layer: engines
Purpose: Meta-engine that reads active quests and recent events each tick, then writes
         max_event_severity and quest_generation_rate multipliers to WorldState so other
         engines can gate their sampling accordingly.
Does NOT: call LLMs, create graph nodes/edges, expose HTTP routes, open sessions,
          or import the graph layer.
Dependencies: engines.story_pacing.pacing_rules_loader, engines.ports.story_pacing_port,
              engines.ports.world_state_port
Dependencies injected: PacingRules, StoryPacingGraphPort, WorldStateGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from npc_engine.config import get_settings
from npc_engine.engines.ports.story_pacing_port import StoryPacingGraphPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort
from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules

_LOGGER = logging.getLogger(__name__)


class StoryPacingEngine:
    """Gates high-severity events and new quest generation based on active quest state.

    On each tick:
    1. Queries active quests with severity >= high_severity_quest_threshold.
    2. Queries recent major events within the cooldown window.
    3. Computes new max_event_severity and quest_generation_rate.
    4. Writes updated values to WorldState.
    """

    def __init__(
        self,
        rules: PacingRules,
        story_pacing_repo: StoryPacingGraphPort,
        world_state_repo: WorldStateGraphPort,
    ) -> None:
        """Initialise the engine with a loaded rule set and graph ports.

        Args:
            rules: Validated PacingRules loaded from pacing_rules.yaml.
            story_pacing_repo: Graph reads for active quests + recent major events.
            world_state_repo: Shared graph port for reading/upserting WorldState.
        """
        self._rules = rules
        self._story_pacing_repo = story_pacing_repo
        self._world_state_repo = world_state_repo
        self._lock = asyncio.Lock()

    async def run_tick(self, *, tick_id: int, **_: Any) -> dict[str, Any]:
        """Execute one story pacing tick: evaluate suppression and update WorldState.

        Args:
            tick_id: Current game tick identifier.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; graph access is via
                the injected ports, DEC-122 / SEV-24).

        Returns:
            Dict with max_event_severity (int), quest_generation_rate (float),
            and suppressed (bool).
        """
        async with self._lock:
            high_severity_quests = await self._get_active_high_severity_quests()
            recent_major_events = await self._get_recent_major_events(tick_id)

            suppressed = len(high_severity_quests) > 0
            relaxed_after_cooldown = len(recent_major_events) == 0 and not suppressed

            if suppressed:
                max_event_severity = self._rules.suppression_event_severity_cap
                quest_generation_rate = self._rules.suppression_quest_rate
            else:
                max_event_severity = 100
                quest_generation_rate = 1.0

            world_state = await self._world_state_repo.get_world_state(
                world_id=get_settings().WORLD_ID
            )
            updated = world_state.model_copy(
                update={
                    "max_event_severity": max_event_severity,
                    "quest_generation_rate": quest_generation_rate,
                }
            )
            await self._world_state_repo.upsert_world_state(world_state=updated)

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

    async def _get_active_high_severity_quests(self) -> list[dict[str, Any]]:
        """Query active quests with severity at or above the suppression threshold.

        Returns:
            List of dicts with quest_id and severity keys.
        """
        return await self._story_pacing_repo.get_active_high_severity_quests(
            threshold=self._rules.high_severity_quest_threshold,
        )

    async def _get_recent_major_events(self, tick_id: int) -> list[dict[str, Any]]:
        """Query major events that occurred within the cooldown window.

        Args:
            tick_id: Current tick; events at tick_id - cooldown_ticks or newer are checked.

        Returns:
            List of dicts with event_id, severity, and tick_id keys.
        """
        min_tick = max(0, tick_id - self._rules.cooldown_ticks)
        return await self._story_pacing_repo.get_recent_major_events(
            min_tick_id=min_tick,
            floor=self._rules.major_event_severity_floor,
        )
