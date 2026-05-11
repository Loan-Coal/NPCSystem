"""
Module: schedule_service
Layer: graph
Purpose: Session-scoped service for Schedule CRUD and character assignment.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.schedules
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.graph.schedule_queries import (
    get_character_location_at,
    get_character_schedule,
    get_characters_at_location,
    get_schedule,
)
from npc_engine.graph.schedule_writer import (
    assign_schedule,
    unassign_schedule,
    upsert_schedule,
)
from npc_engine.utils.errors import ScheduleNotFoundError

_VALID_TIMES = frozenset({"morning", "midday", "afternoon", "evening", "night"})


class ScheduleService:
    """Session-scoped service for Schedule node CRUD and character assignment.

    Mutations open an explicit transaction so that Cypher errors roll back
    cleanly. Reads run directly on the session (auto-commit reads).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the service with an injected Neo4j session.

        Args:
            session: Active Neo4j async session for the current request.
        """
        self._session = session

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def create_schedule(
        self,
        *,
        schedule_id: str,
        name: str,
        description: str | None,
        entries: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Create or update a Schedule node.

        Args:
            schedule_id: Unique identifier for the schedule.
            name: Human-readable display name.
            description: Optional freeform description.
            entries: List of dicts with keys ``time_of_day``, ``location_id``,
                and optionally ``activity``.

        Returns:
            Dict of schedule properties as stored.

        Raises:
            ValueError: If any entry contains an invalid ``time_of_day`` value.
        """
        for entry in entries:
            tod = entry.get("time_of_day", "")
            if tod not in _VALID_TIMES:
                raise ValueError(
                    f"Invalid time_of_day '{tod}'. Must be one of: {sorted(_VALID_TIMES)}"
                )

        now = datetime.now(timezone.utc).isoformat()
        properties: dict[str, Any] = {
            "id": schedule_id,
            "name": name,
            "description": description,
            "entries": json.dumps(entries),
            "created_at": now,
            "last_graph_updated_at": now,
        }
        tx = await self._session.begin_transaction()
        async with tx:
            await upsert_schedule(tx, schedule_id=schedule_id, properties=properties)
        return properties

    async def assign_schedule(self, *, character_id: str, schedule_id: str) -> None:
        """Assign a Schedule to a Character, replacing any existing assignment.

        Args:
            character_id: ID of the character node.
            schedule_id: ID of the schedule node.

        Raises:
            ScheduleAssignmentError: If either node does not exist.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            await assign_schedule(tx, character_id=character_id, schedule_id=schedule_id)

    async def unassign_schedule(self, *, character_id: str) -> None:
        """Remove a Character's FOLLOWS_SCHEDULE edge, if any.

        Args:
            character_id: ID of the character node.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            await unassign_schedule(tx, character_id=character_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_schedule(self, schedule_id: str) -> dict[str, Any]:
        """Fetch a Schedule node by ID.

        Args:
            schedule_id: ID of the schedule node.

        Returns:
            Dict of schedule properties.

        Raises:
            ScheduleNotFoundError: If the node does not exist.
        """
        result = await get_schedule(self._session, schedule_id)
        if result is None:
            raise ScheduleNotFoundError(schedule_id=schedule_id)
        return cast(dict[str, Any], result)

    async def get_character_schedule(self, character_id: str) -> dict[str, Any] | None:
        """Fetch the Schedule a character follows, or None if unassigned.

        Args:
            character_id: ID of the character node.

        Returns:
            Dict of schedule properties, or None.
        """
        return cast(
            dict[str, Any] | None,
            await get_character_schedule(self._session, character_id),
        )

    async def get_character_location_at(
        self, character_id: str, time_of_day: str
    ) -> str | None:
        """Return the location_id from a character's schedule at a given time of day.

        Args:
            character_id: ID of the character node.
            time_of_day: One of morning | midday | afternoon | evening | night.

        Returns:
            location_id string, or None if no matching entry or no schedule.

        Raises:
            ValueError: If time_of_day is not a valid enum value.
        """
        if time_of_day not in _VALID_TIMES:
            raise ValueError(
                f"Invalid time_of_day '{time_of_day}'. Must be one of: {sorted(_VALID_TIMES)}"
            )
        return await get_character_location_at(self._session, character_id, time_of_day)

    async def get_characters_at_location(
        self, location_id: str, time_of_day: str
    ) -> list[str]:
        """Return character IDs scheduled to be at a location at a given time of day.

        Args:
            location_id: ID of the location node.
            time_of_day: One of morning | midday | afternoon | evening | night.

        Returns:
            List of character_id strings.

        Raises:
            ValueError: If time_of_day is not a valid enum value.
        """
        if time_of_day not in _VALID_TIMES:
            raise ValueError(
                f"Invalid time_of_day '{time_of_day}'. Must be one of: {sorted(_VALID_TIMES)}"
            )
        return await get_characters_at_location(self._session, location_id, time_of_day)
