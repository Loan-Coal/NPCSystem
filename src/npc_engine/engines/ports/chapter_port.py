"""
Module: chapter_port
Layer: engines
Purpose: Structural Protocol for the chapter graph domain — reads and writes the
         ChapterEngine needs (current chapter, quest density, beat intensity, recent
         events, faction standings for labelling context, plus chapter create/close
         and event linkage), so the engine depends on an abstraction instead of
         importing graph query/writer functions and holding a Neo4j session.
         Implemented in graph/repositories/chapter_repository.py.
Does NOT: open sessions, run Cypher, label chapters, call LLMs, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.chapter.chapter_engine; implemented structurally by
         npc_engine.graph.repositories.chapter_repository.Neo4jChapterRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class ChapterGraphPort(Protocol):
    """Chapter-domain graph reads/writes required by ChapterEngine."""

    async def get_current_chapter(self) -> dict[str, Any] | None:
        """Return the currently open chapter (or None when none is open)."""
        ...

    async def count_completed_quests_since_tick(self, *, since_tick: int) -> int:
        """Return the number of quests completed at or after since_tick."""
        ...

    async def get_completed_quests_since_tick(self, *, since_tick: int) -> list[dict[str, Any]]:
        """Return quests completed at or after since_tick for labelling context."""
        ...

    async def get_max_beat_intensity_in_chapter(self, *, chapter_id: str) -> int:
        """Return the maximum narrative-beat intensity in a chapter (0 if none)."""
        ...

    async def get_recent_events_for_chapter(
        self, *, since_tick: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return recent events at or after since_tick for labelling/linkage."""
        ...

    async def get_faction_standings_summary(self, *, limit: int = 5) -> list[dict[str, Any]]:
        """Return the top factions by power_score for chapter-labelling context."""
        ...

    async def create_chapter(
        self,
        *,
        chapter_id: str,
        name: str,
        started_at_tick: int,
        theme: str | None = None,
        status: str = "open",
    ) -> str:
        """Create or upsert a CHAPTER node; return its id."""
        ...

    async def close_chapter(self, *, chapter_id: str, ended_at_tick: int) -> None:
        """Mark a chapter closed (ended_at_tick + status='closed')."""
        ...

    async def link_event_to_chapter(
        self, *, event_id: str, chapter_id: str, tick_id: int
    ) -> None:
        """Create the PART_OF_CHAPTER edge from an Event to a Chapter (idempotent)."""
        ...
