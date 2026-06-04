"""
Module: skill_progression_engine
Layer: engines
Purpose: Awards XP to characters who participated in recently-completed quests,
         based on skills required by the quest's template.
Does NOT: call LLMs, define quest templates, or update non-skill graph state.
Dependencies: graph.skill_queries, graph.skill_service
Dependencies injected: AsyncSession, xp_per_completion (constructor).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.skill_queries import get_completed_quests_with_skills
from npc_engine.graph.skill_service import increment_xp

_LOGGER = logging.getLogger(__name__)


class SkillProgressionEngine:
    """Awards XP for skills required by quests that completed this tick.

    On each tick, queries for quests marked ``status='completed'`` at the current
    tick that have an associated ``QuestTemplate`` with ``REQUIRES_SKILL`` edges.
    For each (character, skill) pair found, calls ``increment_xp`` with the
    configured ``xp_per_completion``.
    """

    def __init__(self, xp_per_completion: int = 50) -> None:
        """Initialise the skill progression engine.

        Args:
            xp_per_completion: XP awarded per skill per quest completion.
        """
        self._xp_per_completion = xp_per_completion

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict[str, Any]:
        """Award XP for quest completions that occurred this tick.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick.

        Returns:
            Dict with key ``xp_awards`` (number of (character, skill) XP grants made).
        """
        rows = await get_completed_quests_with_skills(session, tick_id=tick_id)
        awards = 0
        for row in rows:
            try:
                new_level = await increment_xp(
                    session,
                    character_id=row["character_id"],
                    skill_id=row["skill_id"],
                    xp_delta=self._xp_per_completion,
                    tick=tick_id,
                )
                _LOGGER.debug(
                    "skill_progression: char=%s skill=%s new_level=%d (quest=%s)",
                    row["character_id"],
                    row["skill_id"],
                    new_level,
                    row["quest_id"],
                )
                awards += 1
            except Exception:
                _LOGGER.exception(
                    "skill_progression: failed to award XP to char=%s for skill=%s",
                    row.get("character_id"),
                    row.get("skill_id"),
                )
        return {"xp_awards": awards}
