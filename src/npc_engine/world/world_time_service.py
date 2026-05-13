"""
Module: world_time_service
Layer: retrieval (world sub-package)
Purpose: Pure function for advancing structured game time by one step in a named field.
Does NOT: read or write graph state; make network or I/O calls.
Dependencies: world.world_state, world.time_utils
Dependencies injected: None.
Used by: api.routes.clock
"""

from __future__ import annotations

from npc_engine.world.time_utils import DAYS_PER_SEASON, SEASONS, TIME_OF_DAY_SLOTS
from npc_engine.world.world_state import WorldState

_VALID_FIELDS: frozenset[str] = frozenset({"time_of_day", "day", "season", "year"})


def advance_time(field: str, world_state: WorldState) -> WorldState:
    """Return a new WorldState with the named time field advanced by one step.

    Wrap-around rules:
      - time_of_day: cycles morning→midday→afternoon→evening→night→morning;
        night→morning also increments day.
      - day: 1–28; day 29 resets to 1 and advances season.
      - season: cycles spring→summer→autumn→winter→spring;
        winter→spring also increments year.
      - year: increments indefinitely, never wraps.

    Args:
        field: One of "time_of_day", "day", "season", "year".
        world_state: Current immutable WorldState.

    Returns:
        New WorldState with the specified field (and any cascading fields) updated.

    Raises:
        ValueError: If field is not one of the recognised time fields.
    """
    if field not in _VALID_FIELDS:
        raise ValueError(f"Unknown time field '{field}'. Must be one of {sorted(_VALID_FIELDS)}.")

    if field == "time_of_day":
        return _advance_time_of_day(world_state)
    if field == "day":
        return _advance_day(world_state)
    if field == "season":
        return _advance_season(world_state)
    return _advance_year(world_state)


def _advance_time_of_day(world_state: WorldState) -> WorldState:
    """Cycle time_of_day; wrap night→morning increments day."""
    current_idx = TIME_OF_DAY_SLOTS.index(world_state.time_of_day) if world_state.time_of_day in TIME_OF_DAY_SLOTS else 0
    next_idx = (current_idx + 1) % len(TIME_OF_DAY_SLOTS)
    next_slot = TIME_OF_DAY_SLOTS[next_idx]
    update: dict[str, object] = {"time_of_day": next_slot}
    if next_slot == "morning":
        wrapped = _advance_day(world_state)
        return wrapped.model_copy(update={"time_of_day": next_slot})
    return world_state.model_copy(update=update)


def _advance_day(world_state: WorldState) -> WorldState:
    """Increment day; wrap at DAYS_PER_SEASON advances season."""
    if world_state.day >= DAYS_PER_SEASON:
        advanced_season = _advance_season(world_state)
        return advanced_season.model_copy(update={"day": 1})
    return world_state.model_copy(update={"day": world_state.day + 1})


def _advance_season(world_state: WorldState) -> WorldState:
    """Cycle season; wrap winter→spring increments year."""
    current_idx = SEASONS.index(world_state.season) if world_state.season in SEASONS else 0
    next_idx = (current_idx + 1) % len(SEASONS)
    next_season = SEASONS[next_idx]
    update: dict[str, object] = {"season": next_season}
    if next_season == "spring":
        update["year"] = world_state.year + 1
    return world_state.model_copy(update=update)


def _advance_year(world_state: WorldState) -> WorldState:
    """Increment year; no upper bound."""
    return world_state.model_copy(update={"year": world_state.year + 1})
