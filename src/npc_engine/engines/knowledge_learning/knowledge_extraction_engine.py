"""
Module: knowledge_extraction_engine
Layer: engines
Purpose: Extracts player-stated facts from dialogue and writes them as NPC belief nodes,
         skipping facts that duplicate an existing belief (EXP-215 slice 1).
Does NOT: call LLMs or validate facts semantically — raw fact strings come pre-extracted
          from DialogueResponse. Does NOT perform semantic contradiction detection (slice 2).
Dependencies: graph.knowledge_writer, graph.belief_queries, engines.knowledge_learning.models
Dependencies injected: AsyncSession (per call), config via constructor.
Used by: engines.dialogue.dialogue_handler
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.knowledge_learning.models import KnowledgeExtractionResult
from npc_engine.graph.belief_queries import find_conflicting_belief
from npc_engine.graph.knowledge_writer import write_belief

_logger = logging.getLogger(__name__)

_FACT_MIN_LEN: int = 5
_FACT_MAX_LEN: int = 300
_DEFAULT_CONFIDENCE: int = 70


def _is_valid_fact(fact_str: str) -> bool:
    """Return True when fact_str is within the accepted length bounds."""
    return _FACT_MIN_LEN <= len(fact_str) <= _FACT_MAX_LEN


class KnowledgeExtractionEngine:
    """Engine that persists player-stated facts as belief nodes on an NPC.

    Each valid fact from the dialogue LLM output is written via the
    graph-layer knowledge_writer, unless a duplicate belief already exists
    (EXP-215 slice 1: case-insensitive exact-content match).
    Semantic contradiction detection is deferred to slice 2.

    Injected dependencies: none (stateless; all I/O is delegated to
    find_conflicting_belief and write_belief which receive the session per call).
    """

    async def process(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        player_id: str,
        tick: int,
        learned_facts: list[str],
        game_time_str: str,
    ) -> KnowledgeExtractionResult:
        """Write each valid, non-duplicate player-stated fact as a belief node on the NPC.

        Facts shorter than 5 chars or longer than 300 chars are skipped.
        Facts that duplicate an existing belief (case-insensitive exact match) are skipped
        and logged (EXP-215 slice 1).  Semantic contradiction detection is slice 2.

        Args:
            session: Active Neo4j async session.
            npc_id: ID of the NPC who learned the facts.
            player_id: ID of the player who stated the facts.
            tick: Current game tick (stored as provenance on the BELIEVES edge).
            learned_facts: Raw fact strings extracted from the LLM output.
            game_time_str: Human-readable game-time string for the belief node.

        Returns:
            KnowledgeExtractionResult with counts of written and skipped facts.
        """
        written = 0
        skipped = 0
        for fact_str in learned_facts:
            if not _is_valid_fact(fact_str):
                skipped += 1
                continue
            if await self._is_duplicate(session, npc_id=npc_id, fact_str=fact_str):
                skipped += 1
                continue
            await self._persist_fact(session, npc_id=npc_id, player_id=player_id,
                                     tick=tick, fact_str=fact_str, game_time_str=game_time_str)
            written += 1
        return KnowledgeExtractionResult(written=written, skipped=skipped)

    async def _is_duplicate(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        fact_str: str,
    ) -> bool:
        """Return True when an identical belief already exists for the NPC."""
        existing = await find_conflicting_belief(session, character_id=npc_id, content=fact_str)
        if existing is not None:
            _logger.info(
                "belief_skipped_duplicate",
                extra={"npc_id": npc_id, "existing_id": existing.get("id"), "content": fact_str},
            )
            return True
        return False

    async def _persist_fact(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        player_id: str,
        tick: int,
        fact_str: str,
        game_time_str: str,
    ) -> None:
        """Write one validated fact as a belief node and log it."""
        await write_belief(
            session,
            npc_id=npc_id,
            content=fact_str,
            confidence=_DEFAULT_CONFIDENCE,
            source_character_id=player_id,
            learned_at_tick=tick,
            game_time_str=game_time_str,
        )
        _logger.info("belief_written", extra={"npc_id": npc_id, "player_id": player_id, "tick": tick})
