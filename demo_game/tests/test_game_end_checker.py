"""
Tests for demo_game.game_end_checker.

All tests are pure (no I/O, no network). They exercise:
- check_win: standing threshold + faction count
- check_lose: iron_legion control of market square
- evaluate_game_end: integrated outcome derivation
"""

from __future__ import annotations

import pytest

from demo_game.game_end_checker import (
    ARC_WIN_SUBTITLES,
    DEMO_FACTIONS,
    LOSE_LOCATION_ID,
    WIN_MIN_FACTIONS,
    WIN_STANDING_THRESHOLD,
    ObjectiveState,
    check_lose,
    check_win,
    detect_first_allied_faction,
    evaluate_game_end,
)


# ---------------------------------------------------------------------------
# check_win
# ---------------------------------------------------------------------------


def test_check_win_two_factions_at_threshold_returns_true():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "city_guard": WIN_STANDING_THRESHOLD,
        "thieves_guild": 0,
    }
    assert check_win(standings) is True


def test_check_win_all_three_factions_returns_true():
    standings = {f: WIN_STANDING_THRESHOLD + 10 for f in DEMO_FACTIONS}
    assert check_win(standings) is True


def test_check_win_one_faction_returns_false():
    standings = {"merchants_guild": 100, "city_guard": 0, "thieves_guild": 0}
    assert check_win(standings) is False


def test_check_win_below_threshold_returns_false():
    standings = {f: WIN_STANDING_THRESHOLD - 1 for f in DEMO_FACTIONS}
    assert check_win(standings) is False


def test_check_win_empty_standings_returns_false():
    assert check_win({}) is False


def test_check_win_unknown_factions_ignored():
    standings = {
        "merchants_guild": 100,
        "city_guard": 100,
        "iron_legion": 100,  # not a demo faction
    }
    assert check_win(standings) is True


def test_check_win_minimum_threshold_boundary():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "city_guard": WIN_STANDING_THRESHOLD - 1,
        "thieves_guild": 0,
    }
    assert check_win(standings) is False


# ---------------------------------------------------------------------------
# check_lose
# ---------------------------------------------------------------------------


def test_check_lose_lose_location_controlled_returns_true():
    assert check_lose([LOSE_LOCATION_ID]) is True


def test_check_lose_other_location_controlled_returns_false():
    assert check_lose(["loc_tavern"]) is False


def test_check_lose_empty_list_returns_false():
    assert check_lose([]) is False


def test_check_lose_multiple_locations_including_lose_location():
    assert check_lose(["loc_tavern", LOSE_LOCATION_ID]) is True


# ---------------------------------------------------------------------------
# evaluate_game_end
# ---------------------------------------------------------------------------


def test_evaluate_game_end_no_outcome():
    state = evaluate_game_end(
        reputation_records=[
            {"faction_id": "merchants_guild", "standing": 10},
        ],
        iron_legion_controls=[],
    )
    assert state.outcome is None
    assert state.faction_standings["merchants_guild"] == 10


def test_evaluate_game_end_win():
    records = [
        {"faction_id": "merchants_guild", "standing": 60},
        {"faction_id": "city_guard", "standing": 70},
    ]
    state = evaluate_game_end(records, iron_legion_controls=[])
    assert state.outcome == "win"


def test_evaluate_game_end_lose():
    records = [{"faction_id": "merchants_guild", "standing": 0}]
    state = evaluate_game_end(records, iron_legion_controls=[LOSE_LOCATION_ID])
    assert state.outcome == "lose"


def test_evaluate_game_end_lose_takes_priority_over_win():
    """Lose condition is checked first so it dominates even if win is met."""
    records = [
        {"faction_id": "merchants_guild", "standing": 100},
        {"faction_id": "city_guard", "standing": 100},
    ]
    state = evaluate_game_end(records, iron_legion_controls=[LOSE_LOCATION_ID])
    assert state.outcome == "lose"


def test_evaluate_game_end_returns_objective_state_type():
    state = evaluate_game_end([], [])
    assert isinstance(state, ObjectiveState)


def test_evaluate_game_end_iron_legion_controls_stored():
    state = evaluate_game_end([], [LOSE_LOCATION_ID])
    assert LOSE_LOCATION_ID in state.iron_legion_controls


def test_evaluate_game_end_faction_standings_defaults_to_zero():
    state = evaluate_game_end([], [])
    for faction in DEMO_FACTIONS:
        assert state.faction_standings.get(faction, 0) == 0


# ---------------------------------------------------------------------------
# detect_first_allied_faction
# ---------------------------------------------------------------------------


def test_detect_first_allied_empty_standings_returns_none():
    assert detect_first_allied_faction({}) is None


def test_detect_first_allied_no_faction_at_threshold_returns_none():
    standings = {f: WIN_STANDING_THRESHOLD - 1 for f in DEMO_FACTIONS}
    assert detect_first_allied_faction(standings) is None


def test_detect_first_allied_single_qualified_faction():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "city_guard": 0,
        "thieves_guild": 0,
    }
    assert detect_first_allied_faction(standings) == "merchants_guild"


def test_detect_first_allied_picks_highest_standing():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "city_guard": WIN_STANDING_THRESHOLD + 20,
        "thieves_guild": WIN_STANDING_THRESHOLD + 10,
    }
    assert detect_first_allied_faction(standings) == "city_guard"


def test_detect_first_allied_ignores_non_demo_factions():
    standings = {
        "iron_legion": 999,
        "merchants_guild": WIN_STANDING_THRESHOLD,
    }
    assert detect_first_allied_faction(standings) == "merchants_guild"


# ---------------------------------------------------------------------------
# ARC_WIN_SUBTITLES
# ---------------------------------------------------------------------------


def test_arc_win_subtitles_covers_all_demo_factions():
    for faction in DEMO_FACTIONS:
        assert faction in ARC_WIN_SUBTITLES, f"Missing subtitle for {faction}"


def test_arc_win_subtitles_has_default_key():
    assert None in ARC_WIN_SUBTITLES


def test_arc_win_subtitles_values_are_non_empty_strings():
    for key, value in ARC_WIN_SUBTITLES.items():
        assert isinstance(value, str) and value.strip(), f"Empty subtitle for key {key!r}"


# ---------------------------------------------------------------------------
# arc_faction in evaluate_game_end
# ---------------------------------------------------------------------------


def test_evaluate_game_end_arc_faction_stored():
    records = [{"faction_id": "merchants_guild", "standing": 60}]
    state = evaluate_game_end(records, iron_legion_controls=[], arc_faction="merchants_guild")
    assert state.arc_faction == "merchants_guild"


def test_evaluate_game_end_arc_faction_defaults_none():
    state = evaluate_game_end([], [])
    assert state.arc_faction is None


def test_evaluate_game_end_arc_faction_preserved_on_lose():
    records = [
        {"faction_id": "merchants_guild", "standing": 60},
        {"faction_id": "city_guard", "standing": 60},
    ]
    state = evaluate_game_end(
        records,
        iron_legion_controls=[LOSE_LOCATION_ID],
        arc_faction="city_guard",
    )
    assert state.outcome == "lose"
    assert state.arc_faction == "city_guard"
