"""
Module: time_utils
Layer: retrieval (world sub-package)
Purpose: Pure helpers for game-time distance calculation and human-readable time labels.
Does NOT: read or write graph state; make network or I/O calls; import from graph/ or engines/.
Dependencies: None — stdlib dataclasses only.
Dependencies injected: None.
Used by: world.world_time_service, dialogue context builders (future).
"""

from __future__ import annotations

from dataclasses import dataclass

SEASONS: tuple[str, ...] = ("spring", "summer", "autumn", "winter")
TIME_OF_DAY_SLOTS: tuple[str, ...] = ("morning", "midday", "afternoon", "evening", "night")
DAYS_PER_SEASON: int = 28


@dataclass(frozen=True)
class TimePoint:
    """Immutable snapshot of structured game time."""

    year: int
    season: str
    day: int
    time_of_day: str


def _total_days(tp: TimePoint) -> int:
    """Convert a TimePoint to a monotonically increasing day count.

    Args:
        tp: The time point to convert.

    Returns:
        Absolute day count since year 0, season 0, day 0.
    """
    season_index = SEASONS.index(tp.season) if tp.season in SEASONS else 0
    return tp.year * len(SEASONS) * DAYS_PER_SEASON + season_index * DAYS_PER_SEASON + tp.day


def how_long_ago(from_: TimePoint, to: TimePoint) -> str:
    """Return a human-friendly label for the time distance between two TimePoints.

    Buckets (from_ is 'now', to is the earlier point):
      - same day and same time_of_day  → "moments ago"
      - same day, different time_of_day → "earlier today"
      - 1 day                           → "yesterday"
      - 2–27 days                       → "a few days ago"
      - 28 days (one full season)       → "last season"
      - more than 28 days               → "long ago"

    Args:
        from_: The reference point (current time).
        to: The earlier point being described.

    Returns:
        Human-readable time-distance string.
    """
    delta_days = _total_days(from_) - _total_days(to)
    if delta_days == 0:
        if from_.time_of_day == to.time_of_day:
            return "moments ago"
        return "earlier today"
    if delta_days == 1:
        return "yesterday"
    if delta_days < DAYS_PER_SEASON:
        return "a few days ago"
    if delta_days == DAYS_PER_SEASON:
        return "last season"
    return "long ago"
