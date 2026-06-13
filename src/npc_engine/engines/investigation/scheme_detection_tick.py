"""
Module: scheme_detection_tick
Layer: engines
Purpose: Tick-scheduler adapter that discovers active schemes (F1.6 detection-half /
         DEC-107). On its cadence it flips schemes that have accrued enough covert
         steps AND whose owner is witnessed (co-located) to status 'discovered'.
Does NOT: call LLMs, create nodes/edges, change type_registry YAML, or advance
          schemes (that is SchemeAdvanceTick's job). Schema-free: only mutates the
          existing Scheme.status free-string field.
Dependencies injected: Settings (constructor); AsyncSession (per call).
Used by: scheduler/tick_scheduler.py (scheme_detection_engine slot); wired in
         api/dependencies_engines.get_scheme_detection_tick.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.scheme_reader import get_discoverable_scheme_ids
from npc_engine.graph.scheme_writer import mark_scheme_discovered

_LOGGER = logging.getLogger(__name__)


class SchemeDetectionTick:
    """Discovers witnessed, sufficiently-advanced active schemes on a tick cadence.

    Self-gates on SCHEME_DETECTION_TICK_INTERVAL. A scheme is discoverable when it
    has at least SCHEME_DISCOVERY_MIN_STEPS covert steps and its owner shares a
    location with another character. Discovery flips Scheme.status 'active'→
    'discovered' (no new node/edge — schema-free).
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the detection tick adapter.

        Args:
            settings: Application settings (cadence + discovery step threshold).
        """
        self._interval = settings.SCHEME_DETECTION_TICK_INTERVAL
        self._min_steps = settings.SCHEME_DISCOVERY_MIN_STEPS

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict[str, Any]:
        """Discover eligible active schemes, on cadence.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick.

        Returns:
            Dict with ``tick_id``, ``discovered`` (count), and ``skipped`` (bool).
        """
        if tick_id % self._interval != 0:
            return {"tick_id": tick_id, "discovered": 0, "skipped": True}

        scheme_ids = await get_discoverable_scheme_ids(session, self._min_steps)
        discovered = 0
        for scheme_id in scheme_ids:
            if await mark_scheme_discovered(session, scheme_id):
                discovered += 1
        if discovered:
            _LOGGER.debug("scheme_detection tick %d: discovered %d", tick_id, discovered)
        return {"tick_id": tick_id, "discovered": discovered, "skipped": False}
