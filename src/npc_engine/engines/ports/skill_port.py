"""
Module: skill_port
Layer: engines
Purpose: Structural Protocol for the skill graph domain (read quests completed this
         tick with their required skills; increment a character's skill XP), so
         SkillProgressionEngine depends on an abstraction instead of importing
         skill_queries/skill_service and holding a Neo4j session. Implemented in
         graph/repositories/skill_repository.py.
Does NOT: open sessions, run Cypher, define XP rules, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.skill.skill_progression_engine; implemented structurally by
         npc_engine.graph.repositories.skill_repository.Neo4jSkillRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class SkillGraphPort(Protocol):
    """Graph operations required by SkillProgressionEngine (read completions, write XP)."""

    async def get_completed_quests_with_skills(self, *, tick_id: int) -> list[dict[str, Any]]:
        """Return (quest, character, skill) rows for quests completed at the given tick."""
        ...

    async def increment_xp(
        self, *, character_id: str, skill_id: str, xp_delta: int, tick: int
    ) -> int:
        """Add XP to a character's skill and return the new level."""
        ...
