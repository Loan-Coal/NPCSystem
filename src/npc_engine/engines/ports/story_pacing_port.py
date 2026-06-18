"""
Module: story_pacing_port
Layer: engines
Purpose: Structural Protocol for the story-pacing graph reads (active high-severity quests,
         recent major events), so StoryPacingEngine depends on an abstraction instead of
         importing story_pacing_queries and holding a Neo4j session. WorldState read/upsert
         is a separate shared port (world_state_port). Implemented in
         graph/repositories/story_pacing_repository.py.
Does NOT: open sessions, run Cypher, compute pacing multipliers, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.story_pacing.story_pacing_engine; implemented structurally by
         npc_engine.graph.repositories.story_pacing_repository.Neo4jStoryPacingRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class StoryPacingGraphPort(Protocol):
    """Story-pacing graph reads required by StoryPacingEngine."""

    async def get_active_high_severity_quests(self, *, threshold: int) -> list[dict[str, Any]]:
        """Return active quests with severity at or above the threshold."""
        ...

    async def get_recent_major_events(
        self, *, min_tick_id: int, floor: int
    ) -> list[dict[str, Any]]:
        """Return major events at or after min_tick_id with severity at or above floor."""
        ...
