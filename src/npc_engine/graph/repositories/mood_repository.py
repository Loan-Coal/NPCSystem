"""
Module: mood_repository
Layer: graph
Purpose: Neo4j adapter for the mood graph domain. Opens a session per operation from
         the injected GraphDB and delegates to mood_queries, so MoodContagionEngine
         depends on the abstraction and holds no session. Swap seam for cache/alternate
         DB/microservice backends (DEC-122 / SEV-24).
Does NOT: blend moods, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.social.get_mood_contagion_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.mood_queries import (
    get_all_character_moods,
    get_co_located_affectionate_pairs,
    set_character_mood,
)


class Neo4jMoodRepository:
    """Session-per-call Neo4j adapter for the mood domain (MoodGraphPort).

    Holds the long-lived GraphDB driver holder and opens one session per operation,
    so it is safe to construct once as a process singleton and inject into the
    singleton MoodContagionEngine.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_all_character_moods(self) -> list[dict[str, Any]]:
        """Open a session and return all stored character moods.

        Returns:
            List of dicts with keys character_id, mood, intensity.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_character_moods(session)

    async def get_co_located_affectionate_pairs(
        self, *, affection_threshold: int
    ) -> list[tuple[str, str]]:
        """Open a session and return co-located affectionate NPC pairs.

        Args:
            affection_threshold: Minimum RELATES_TO.affection (exclusive).

        Returns:
            List of (npc_a_id, npc_b_id) tuples.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_co_located_affectionate_pairs(
                session, affection_threshold=affection_threshold
            )

    async def set_character_mood(
        self, *, character_id: str, mood: str, intensity: float
    ) -> None:
        """Open a session and persist a character's mood label + intensity.

        Args:
            character_id: ID of the character node.
            mood: Mood label string.
            intensity: Mood intensity in [0.0, 1.0].
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await set_character_mood(
                session, character_id=character_id, mood=mood, intensity=intensity
            )
