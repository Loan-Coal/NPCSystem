"""
Module: mood_port
Layer: engines
Purpose: Structural Protocol for the mood graph domain (read all character moods,
         read co-located affectionate pairs, persist a character's mood), so
         MoodContagionEngine depends on an abstraction instead of importing
         mood_queries and holding a Neo4j session. Implemented in
         graph/repositories/mood_repository.py, injected at the api composition root.
Does NOT: open sessions, run Cypher, blend moods, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.mood.mood_contagion_engine; implemented structurally by
         npc_engine.graph.repositories.mood_repository.Neo4jMoodRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class MoodGraphPort(Protocol):
    """Graph operations required by MoodContagionEngine (read moods/pairs, write mood)."""

    async def get_all_character_moods(self) -> list[dict[str, Any]]:
        """Return all active characters with a stored mood (character_id, mood, intensity)."""
        ...

    async def get_co_located_affectionate_pairs(
        self, *, affection_threshold: int
    ) -> list[tuple[str, str]]:
        """Return co-located NPC pairs whose RELATES_TO.affection exceeds the threshold."""
        ...

    async def set_character_mood(
        self, *, character_id: str, mood: str, intensity: float
    ) -> None:
        """Persist a character's mood label + intensity to the Character node."""
        ...
