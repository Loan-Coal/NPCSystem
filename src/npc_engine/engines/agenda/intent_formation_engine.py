"""
Module: intent_formation_engine
Layer: engines
Purpose: Tick-scheduler adapter that scores proactive dialogue intents for all
         co-located NPC/player pairs and enqueues those above the threshold.
Does NOT: run Cypher directly; scoring is delegated to conversation_intent_service;
          queue writes are delegated to graph.intent_queue_writer.
Dependencies: engines.agenda.conversation_intent_service,
              graph.intent_queue_writer, graph.player_location_reader, config
Dependencies injected: PlayerLocationReader (via __init__).
Used by: scheduler.tick_scheduler (wired via api.dependencies_engines)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.config import get_settings
from npc_engine.engines.agenda.conversation_intent_service import score_intents
from npc_engine.graph.intent_queue_writer import enqueue_intent, expire_old_intents
from npc_engine.graph.player_location_reader import PlayerLocationReader

# Maximum (npc, player) pairs scored per tick — mirrors ProactiveDialogueTick cap.
MAX_INTENT_CHECKS_PER_TICK: int = 20

_logger = logging.getLogger(__name__)


class IntentFormationEngine:
    """Scores proactive dialogue intents for co-located NPC/player pairs each tick.

    On each call to run_tick:
    1. Fetches co-located (npc, player) pairs via PlayerLocationReader.
    2. Caps the list to MAX_INTENT_CHECKS_PER_TICK.
    3. Runs score_intents() for all pairs concurrently under a semaphore.
    4. Enqueues each formed intent via intent_queue_writer.
    5. Expires stale intents older than INTENT_EXPIRY_TICKS.
    6. Returns {"intents_formed": N, "expired": M}.

    No mutable state beyond injected dependencies — safe for concurrent use.
    """

    def __init__(self, location_reader: PlayerLocationReader) -> None:
        """Initialise the engine with the injected location reader.

        Args:
            location_reader: Provides get_collocated_pairs(session).
        """
        self._location_reader = location_reader

    async def run_tick(
        self,
        session: AsyncSession,
        tick_id: int,
    ) -> dict[str, Any]:
        """Score and enqueue intents for all co-located NPC/player pairs.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick.

        Returns:
            Dict with ``intents_formed`` (count above threshold) and
            ``expired`` (count of stale intents now marked expired).
        """
        settings = get_settings()
        pairs = await self._location_reader.get_collocated_pairs(session)
        capped = pairs[:MAX_INTENT_CHECKS_PER_TICK]

        all_intents = await self._gather_intents(session, capped, tick_id, settings)
        for intent in all_intents:
            await enqueue_intent(session, intent, settings=settings)

        cutoff = max(0, tick_id - settings.INTENT_EXPIRY_TICKS)
        expired = await expire_old_intents(session, cutoff_tick=cutoff)
        _logger.info(
            "intent_formation_tick",
            extra={"tick_id": tick_id, "pairs_checked": len(capped),
                   "intents_formed": len(all_intents), "expired": expired},
        )
        return {"intents_formed": len(all_intents), "expired": expired}

    async def _gather_intents(
        self,
        session: AsyncSession,
        capped: list[tuple[str, str]],
        tick_id: int,
        settings: Any,
    ) -> list[Any]:
        """Score intents for all pairs concurrently under a semaphore.

        Args:
            session: Active Neo4j async session.
            capped: NPC/player pairs to score (already bounded by caller).
            tick_id: Current game tick.
            settings: Application settings providing MAX_CONCURRENT_TICKS.

        Returns:
            Flat list of all ConversationIntent results across all pairs.
        """
        sem = asyncio.Semaphore(settings.MAX_CONCURRENT_TICKS)
        all_intents: list[Any] = []

        async def _score_one(npc_id: str, player_id: str) -> None:
            async with sem:
                results = await score_intents(session, npc_id, player_id, tick_id)
                all_intents.extend(results)

        if capped:
            await asyncio.gather(*(_score_one(npc_id, pid) for npc_id, pid in capped))
        return all_intents
