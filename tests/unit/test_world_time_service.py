"""Unit tests for world.time_utils and world.world_time_service (Phase 3.1)."""

from __future__ import annotations

import pytest

from npc_engine.world.time_utils import DAYS_PER_SEASON, SEASONS, TIME_OF_DAY_SLOTS, TimePoint, how_long_ago
from npc_engine.world.world_state import WorldState
from npc_engine.world.world_time_service import advance_time


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ws(**kwargs) -> WorldState:
    defaults = dict(year=1, season="spring", day=1, time_of_day="morning")
    defaults.update(kwargs)
    return WorldState(**defaults)


# ---------------------------------------------------------------------------
# advance_time — time_of_day
# ---------------------------------------------------------------------------

def test_time_of_day_advances_all_slots():
    ws = _ws(time_of_day="morning")
    for expected in ("midday", "afternoon", "evening", "night", "morning"):
        ws = advance_time("time_of_day", ws)
        assert ws.time_of_day == expected


def test_night_to_morning_increments_day():
    ws = _ws(time_of_day="night", day=1)
    result = advance_time("time_of_day", ws)
    assert result.time_of_day == "morning"
    assert result.day == 2


# ---------------------------------------------------------------------------
# advance_time — day
# ---------------------------------------------------------------------------

def test_day_28_wraps_to_1_and_advances_season():
    ws = _ws(day=DAYS_PER_SEASON, season="spring")
    result = advance_time("day", ws)
    assert result.day == 1
    assert result.season == "summer"


def test_day_below_max_increments_normally():
    ws = _ws(day=5)
    result = advance_time("day", ws)
    assert result.day == 6


# ---------------------------------------------------------------------------
# advance_time — season
# ---------------------------------------------------------------------------

def test_season_wraps_winter_to_spring_increments_year():
    ws = _ws(season="winter", year=1)
    result = advance_time("season", ws)
    assert result.season == "spring"
    assert result.year == 2


def test_season_advances_through_all():
    ws = _ws(season="spring")
    for expected in ("summer", "autumn", "winter", "spring"):
        ws = advance_time("season", ws)
        assert ws.season == expected


# ---------------------------------------------------------------------------
# advance_time — year
# ---------------------------------------------------------------------------

def test_year_increments_indefinitely():
    ws = _ws(year=999)
    result = advance_time("year", ws)
    assert result.year == 1000


# ---------------------------------------------------------------------------
# Purity guarantee
# ---------------------------------------------------------------------------

def test_advance_time_is_pure():
    ws = _ws(year=1, season="spring", day=1, time_of_day="morning")
    _ = advance_time("time_of_day", ws)
    assert ws.year == 1
    assert ws.season == "spring"
    assert ws.day == 1
    assert ws.time_of_day == "morning"


# ---------------------------------------------------------------------------
# Invalid field
# ---------------------------------------------------------------------------

def test_advance_time_invalid_field_raises():
    ws = _ws()
    with pytest.raises(ValueError, match="Unknown time field"):
        advance_time("century", ws)


# ---------------------------------------------------------------------------
# how_long_ago
# ---------------------------------------------------------------------------

def _tp(**kwargs) -> TimePoint:
    defaults = dict(year=1, season="spring", day=1, time_of_day="morning")
    defaults.update(kwargs)
    return TimePoint(**defaults)


def test_how_long_ago_moments():
    now = _tp(year=1, season="spring", day=5, time_of_day="midday")
    then = _tp(year=1, season="spring", day=5, time_of_day="midday")
    assert how_long_ago(now, then) == "moments ago"


def test_how_long_ago_earlier_today():
    now = _tp(year=1, season="spring", day=5, time_of_day="evening")
    then = _tp(year=1, season="spring", day=5, time_of_day="morning")
    assert how_long_ago(now, then) == "earlier today"


def test_how_long_ago_yesterday():
    now = _tp(year=1, season="spring", day=6, time_of_day="morning")
    then = _tp(year=1, season="spring", day=5, time_of_day="morning")
    assert how_long_ago(now, then) == "yesterday"


def test_how_long_ago_few_days():
    now = _tp(year=1, season="spring", day=7, time_of_day="morning")
    then = _tp(year=1, season="spring", day=3, time_of_day="morning")
    assert how_long_ago(now, then) == "a few days ago"


def test_how_long_ago_last_season():
    # exactly 28 days apart
    now = _tp(year=1, season="summer", day=1, time_of_day="morning")
    then = _tp(year=1, season="spring", day=1, time_of_day="morning")
    assert how_long_ago(now, then) == "last season"


def test_how_long_ago_long_ago():
    now = _tp(year=2, season="spring", day=1, time_of_day="morning")
    then = _tp(year=1, season="spring", day=1, time_of_day="morning")
    assert how_long_ago(now, then) == "long ago"
