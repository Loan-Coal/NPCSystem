"""
Module: routine_engine
Layer: engines/routine
Purpose: Moves active characters to their scheduled locations on each game tick.
Does NOT: define scheduling intervals, read world state directly, open sessions,
          or import the graph layer.
Dependencies injected: RoutineGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from npc_engine.engines.ports.routine_port import RoutineGraphPort


LOGGER = logging.getLogger(__name__)


class RoutineEngine:
    """Moves characters to their scheduled locations on each game tick.

    On each tick, queries all active characters with a FOLLOWS_SCHEDULE edge,
    resolves the target location for the given time_of_day (respecting any
    active routine_override), and updates LOCATED_AT edges when the target
    differs from the current location.

    Graph access is injected as a RoutineGraphPort (DEC-122 / SEV-24); the engine
    holds no Neo4j session. The tick scheduler's ``session`` kwarg is accepted and
    ignored until the BaseEngine protocol drops it.
    """

    def __init__(self, routine_repo: RoutineGraphPort) -> None:
        """Initialise the routine engine.

        Args:
            routine_repo: Graph access port (schedule reads, location writes).
        """
        self._routine_repo = routine_repo
        self._lock = asyncio.Lock()

    async def run_tick(
        self,
        *,
        time_of_day: str,
        tick_id: int,
    ) -> dict[str, int]:
        """Execute one routine tick: resolve locations and update LOCATED_AT edges.

        For each active character with a schedule:
        - If a non-expired routine_override exists, use its location_id.
        - If the override is expired, clear it and use the schedule location.
        - If no schedule entry matches time_of_day, skip the character.
        - Move the character only if the target differs from the current location.

        Args:
            time_of_day: Current game time slot (morning/midday/afternoon/evening/night).
            tick_id: Current game tick, used to evaluate override expiry.
            **_: Absorbs the scheduler's ``session`` kwarg (unused; see class docstring).

        Returns:
            Dict with keys ``moved`` (characters relocated) and ``skipped``
            (characters with no matching schedule entry).
        """
        async with self._lock:
            rows = await self._routine_repo.get_scheduled_characters()
            moved = 0
            skipped = 0

            for row in rows:
                target = await self._resolve_target(
                    row=row,
                    time_of_day=time_of_day,
                    tick_id=tick_id,
                )
                if target is None:
                    skipped += 1
                    continue

                current = row.get("current_location_id")
                if current != target:
                    if current is not None:
                        arrived_at_tick = int(row["current_arrived_at_tick"]) if row.get("current_arrived_at_tick") is not None else tick_id
                        await self._routine_repo.record_departure(
                            character_id=row["character_id"],
                            location_id=current,
                            arrived_at_tick=arrived_at_tick,
                            departed_at_tick=tick_id,
                            reason="routine",
                        )
                    await self._routine_repo.update_character_location(
                        character_id=row["character_id"],
                        location_id=target,
                        arrived_at_tick=tick_id,
                    )
                    LOGGER.info(
                        "routine: %s moved to %s at %s",
                        row["character_id"],
                        target,
                        time_of_day,
                    )
                    moved += 1

            return {"moved": moved, "skipped": skipped}

    async def _resolve_target(
        self,
        row: dict[str, Any],
        time_of_day: str,
        tick_id: int,
    ) -> str | None:
        """Return the target location_id for this character at time_of_day.

        Applies override logic: if a valid non-expired override exists, return
        its location; if expired, clear it first. Falls back to schedule entry.

        Args:
            row: Character row from get_scheduled_characters.
            time_of_day: Current time slot.
            tick_id: Current tick for expiry comparison.

        Returns:
            Target location_id, or None if no entry matches.
        """
        override_raw = row.get("routine_override")
        if override_raw:
            try:
                override = json.loads(override_raw)
            except (TypeError, ValueError):
                override = None

            if override and isinstance(override, dict):
                expires_at = override.get("expires_at_tick")
                if expires_at is not None and tick_id < expires_at:
                    return str(override["location_id"])
                # Expired — clear it
                await self._routine_repo.clear_routine_override(
                    character_id=row["character_id"]
                )

        return self._entry_location(row.get("entries_json"), time_of_day)

    @staticmethod
    def _entry_location(entries_json: str | None, time_of_day: str) -> str | None:
        """Parse schedule entries JSON and return the location_id for time_of_day.

        Args:
            entries_json: JSON string of schedule entry dicts.
            time_of_day: Time slot to look up.

        Returns:
            location_id string, or None if no matching entry or parse failure.
        """
        if not entries_json:
            return None
        try:
            entries = json.loads(entries_json)
        except (TypeError, ValueError):
            return None
        for entry in entries:
            if entry.get("time_of_day") == time_of_day:
                loc = entry.get("location_id")
                return str(loc) if loc is not None else None
        return None
