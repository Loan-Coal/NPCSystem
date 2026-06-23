"""
Module: skill_repository
Layer: graph
Purpose: Neo4j adapter for the skill graph domain. Opens a session per operation from
         the injected GraphDB and delegates to skill_queries/skill_service, so
         SkillProgressionEngine depends on the abstraction and holds no session. Swap
         seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: define XP rules, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.progression.get_skill_progression_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.character.skill_queries import get_completed_quests_with_skills
from npc_engine.graph.character.skill_service import increment_xp


class Neo4jSkillRepository:
    """Session-per-call Neo4j adapter for the skill domain (SkillGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_completed_quests_with_skills(self, *, tick_id: int) -> list[dict[str, Any]]:
        """Open a session and return quests completed at the tick with required skills."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_completed_quests_with_skills(session, tick_id=tick_id)

    async def increment_xp(
        self, *, character_id: str, skill_id: str, xp_delta: int, tick: int
    ) -> int:
        """Open a session, add XP to a character's skill, and return the new level."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await increment_xp(
                session,
                character_id=character_id,
                skill_id=skill_id,
                xp_delta=xp_delta,
                tick=tick,
            )
