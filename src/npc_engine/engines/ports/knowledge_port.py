"""
Module: knowledge_port
Layer: engines
Purpose: Structural Protocol for the belief/knowledge graph domain (duplicate-belief
         lookup + belief write-through), so engines that learn or plant beliefs depend
         on one abstraction and hold no Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, validate facts, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/knowledge_learning/knowledge_extraction_engine (and the future deception
         slice, which reuses write_belief); implemented structurally by
         npc_engine.graph.repositories.knowledge_repository.Neo4jKnowledgeRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class KnowledgeGraphPort(Protocol):
    """Read/write access to NPC belief nodes (duplicate lookup + provenance write)."""

    async def find_conflicting_belief(
        self, *, character_id: str, content: str
    ) -> dict[str, Any] | None:
        """Return an existing belief duplicating the candidate content, or None."""
        ...

    async def write_belief(
        self,
        *,
        npc_id: str,
        content: str,
        confidence: int,
        source_character_id: str,
        learned_at_tick: int,
        game_time_str: str,
        is_deception: bool = False,
        deception_goal_id: str | None = None,
    ) -> str:
        """Merge a belief node + BELIEVES edge with provenance; return the belief id."""
        ...
