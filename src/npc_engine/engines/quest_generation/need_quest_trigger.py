"""
Module: need_quest_trigger
Layer: engines
Purpose: Watches for NPCs whose needs have decayed below a threshold and calls
         the quest generator to produce a need-satisfying draft quest for each.
Does NOT: expose HTTP routes, manage quest lifecycle state, or query Neo4j directly.
Dependencies: engines.quest_generation.quest_generation_engine,
              graph.need_queries, graph.need_quest_queries
Dependencies injected: QuestGenerationEngine (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.graph.need_queries import get_all_needs_below_threshold
from npc_engine.graph.need_quest_queries import has_draft_quest

if TYPE_CHECKING:
    from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine

_logger = logging.getLogger(__name__)

DEFAULT_NEED_THRESHOLD: int = 30
_MAX_NEEDS_PER_TICK: int = 10


class NeedQuestTrigger:
    """Generates draft quests for NPCs whose needs have decayed below a threshold.

    On each tick this engine queries for Need nodes whose level is at or below
    ``threshold``.  For each qualifying NPC it skips generation if a draft quest
    already exists (idempotency guard) and otherwise delegates to the injected
    ``QuestGenerationEngine`` to produce a draft quest.

    The ``has_draft_quest`` check is the idempotency guard: if an NPC already has
    an outstanding draft quest it will not receive a second one until the first is
    resolved (offered or removed).
    """

    def __init__(
        self,
        generation_engine: QuestGenerationEngine,
        threshold: int = DEFAULT_NEED_THRESHOLD,
    ) -> None:
        """Initialise the need quest trigger.

        Args:
            generation_engine: Quest generation engine used to create draft quests.
            threshold: Need level at or below which quest generation is triggered.
        """
        self._generation_engine = generation_engine
        self._threshold = threshold

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict:
        """Query for NPCs with critical needs and generate a draft quest for each.

        Caps at ``_MAX_NEEDS_PER_TICK`` needs per tick to bound LLM calls.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier (included in the return payload).

        Returns:
            Dict with ``tick_id``, ``quests_created`` (int), and ``quest_ids`` (list[str]).
        """
        needs = await get_all_needs_below_threshold(session, threshold=self._threshold)
        capped_needs = needs[:_MAX_NEEDS_PER_TICK]
        seen_npcs: set[str] = set()
        quest_ids: list[str] = []

        for need in capped_needs:
            quest_id = await self._process_need(session, need, tick_id, seen_npcs)
            if quest_id is not None:
                quest_ids.append(quest_id)

        _logger.info(
            "need_quest_trigger tick",
            extra={"tick_id": tick_id, "quests_created": len(quest_ids)},
        )
        return {"tick_id": tick_id, "quests_created": len(quest_ids), "quest_ids": quest_ids}

    async def _process_need(
        self,
        session: AsyncSession,
        need: dict,
        tick_id: int,
        seen_npcs: set[str],
    ) -> str | None:
        """Check idempotency and generate a draft quest for a single need row.

        Skips the NPC if it already appeared in this tick (multiple low needs for
        the same NPC) or if it already has a draft quest in the graph.

        Args:
            session: Active Neo4j async session.
            need: Row from get_all_needs_below_threshold (character_id, kind, level).
            tick_id: Current tick (attached to log entries).
            seen_npcs: Mutable set tracking NPCs already processed this tick.

        Returns:
            Quest ID string on success, or None when skipped or on failure.
        """
        character_id: str = str(need["character_id"])
        need_kind: str = str(need["kind"])
        need_level: int = int(need["level"])

        if character_id in seen_npcs:
            return None
        seen_npcs.add(character_id)

        already_has_draft = await has_draft_quest(session, character_id)
        if already_has_draft:
            _logger.info(
                "need_quest_trigger: skipping NPC with existing draft quest",
                extra={"character_id": character_id, "need_kind": need_kind, "tick_id": tick_id},
            )
            return None

        try:
            generated = await self._generation_engine.generate(
                session,
                quest_giver_id=character_id,
            )
        except ValueError as exc:
            _logger.warning(
                "need_quest_trigger: quest generation skipped",
                extra={
                    "character_id": character_id,
                    "need_kind": need_kind,
                    "need_level": need_level,
                    "reason": str(exc),
                    "tick_id": tick_id,
                },
            )
            return None

        _logger.info(
            "need_quest_trigger: quest created",
            extra={
                "character_id": character_id,
                "need_kind": need_kind,
                "need_level": need_level,
                "quest_id": generated.quest_id,
                "tick_id": tick_id,
            },
        )
        return generated.quest_id
