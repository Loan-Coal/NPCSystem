"""
Module: knowledge_extraction_engine
Layer: engines
Purpose: Extracts player-stated facts from dialogue and writes them as NPC belief nodes.
Dependencies: graph.knowledge_writer, engines.knowledge_learning.models
Used by: engines.dialogue.dialogue_handler
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.knowledge_learning.models import KnowledgeExtractionResult
from npc_engine.graph.knowledge_writer import write_belief

_logger = logging.getLogger(__name__)

_FACT_MIN_LEN: int = 5
_FACT_MAX_LEN: int = 300
_DEFAULT_CONFIDENCE: int = 70


class KnowledgeExtractionEngine:
    """Engine that persists player-stated facts as belief nodes on an NPC.

    Each valid fact from the dialogue LLM output is written via the
    graph-layer knowledge_writer.  Contradiction detection and deduplication
    are deferred to slice-3.

    Injected dependencies: none (stateless; all I/O is delegated to
    write_belief which receives the session per call).
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
        """Write each valid player-stated fact as a belief node on the NPC.

        Facts shorter than 5 chars or longer than 300 chars are skipped.
        No deduplication or contradiction detection in this slice.

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
            if len(fact_str) < _FACT_MIN_LEN or len(fact_str) > _FACT_MAX_LEN:
                skipped += 1
                continue

            await write_belief(
                session,
                npc_id=npc_id,
                content=fact_str,
                confidence=_DEFAULT_CONFIDENCE,
                source_character_id=player_id,
                learned_at_tick=tick,
                game_time_str=game_time_str,
            )
            written += 1
            _logger.info(
                "belief_written",
                extra={"npc_id": npc_id, "player_id": player_id, "tick": tick},
            )

        return KnowledgeExtractionResult(written=written, skipped=skipped)
