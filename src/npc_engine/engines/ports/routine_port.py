"""
Module: routine_port
Layer: engines
Purpose: Structural Protocol for the routine graph domain (read scheduled characters,
         update a character's location, clear an expired routine override, and archive
         a departure), so RoutineEngine depends on an abstraction instead of importing
         graph query functions and holding a Neo4j session. Implemented in
         graph/repositories/routine_repository.py.
Does NOT: open sessions, run Cypher, resolve schedules, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.routine.routine_engine; implemented structurally by
         npc_engine.graph.repositories.routine_repository.Neo4jRoutineRepository.

Note: ``record_departure`` belongs to the location-history graph domain; it is folded
in here as RoutineEngine's only location-history call and can be extracted to a shared
location-history port once a second engine needs it.
"""

from __future__ import annotations

from typing import Any, Protocol


class RoutineGraphPort(Protocol):
    """Graph operations required by RoutineEngine (schedule reads + location writes)."""

    async def get_scheduled_characters(self) -> list[dict[str, Any]]:
        """Return active characters that follow a schedule, with their current location."""
        ...

    async def update_character_location(
        self, *, character_id: str, location_id: str, arrived_at_tick: int
    ) -> None:
        """Move a character's LOCATED_AT edge to a new location."""
        ...

    async def clear_routine_override(self, *, character_id: str) -> None:
        """Clear a character's expired routine override."""
        ...

    async def record_departure(
        self,
        *,
        character_id: str,
        location_id: str,
        arrived_at_tick: int,
        departed_at_tick: int,
        reason: str,
    ) -> None:
        """Archive a character's stay at a location as a WAS_AT edge."""
        ...
