"""
Module: knowledge_extraction_engine
Layer: engines
Purpose: Extracts player-stated facts from dialogue and writes them as NPC belief nodes,
         skipping facts that duplicate an existing belief (EXP-215 slice 1).
Does NOT: call LLMs or validate facts semantically — raw fact strings come pre-extracted
          from DialogueResponse. Does NOT perform semantic contradiction detection (slice 2).
          Does NOT open Neo4j sessions — belief reads/writes go through the injected port.
Dependencies: engines.knowledge_learning.models, engines.ports.knowledge_port
Dependencies injected: KnowledgeGraphPort (via constructor).
Used by: engines.dialogue.dialogue_handler
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from npc_engine.engines.knowledge_learning.models import KnowledgeExtractionResult

if TYPE_CHECKING:
    from npc_engine.engines.ports.knowledge_port import KnowledgeGraphPort

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

    Injected dependencies: KnowledgeGraphPort (all belief reads/writes are delegated to
    it; the engine holds no Neo4j session — DEC-122 / SEV-24).
    """

    def __init__(self, *, knowledge_repo: KnowledgeGraphPort) -> None:
        """Store the injected belief-domain repository port.

        Args:
            knowledge_repo: Port for duplicate-belief lookup and belief write-through.
        """
        self._repo = knowledge_repo

    async def process(
        self,
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
            if await self._is_duplicate(npc_id=npc_id, fact_str=fact_str):
                skipped += 1
                continue
            await self._persist_fact(npc_id=npc_id, player_id=player_id,
                                     tick=tick, fact_str=fact_str, game_time_str=game_time_str)
            written += 1
        return KnowledgeExtractionResult(written=written, skipped=skipped)

    async def _is_duplicate(
        self,
        *,
        npc_id: str,
        fact_str: str,
    ) -> bool:
        """Return True when an identical belief already exists for the NPC."""
        existing = await self._repo.find_conflicting_belief(character_id=npc_id, content=fact_str)
        if existing is not None:
            _logger.info(
                "belief_skipped_duplicate",
                extra={"npc_id": npc_id, "existing_id": existing.get("id"), "content": fact_str},
            )
            return True
        return False

    async def _persist_fact(
        self,
        *,
        npc_id: str,
        player_id: str,
        tick: int,
        fact_str: str,
        game_time_str: str,
    ) -> None:
        """Write one validated fact as a belief node and log it."""
        await self._repo.write_belief(
            npc_id=npc_id,
            content=fact_str,
            confidence=_DEFAULT_CONFIDENCE,
            source_character_id=player_id,
            learned_at_tick=tick,
            game_time_str=game_time_str,
        )
        _logger.info("belief_written", extra={"npc_id": npc_id, "player_id": player_id, "tick": tick})
