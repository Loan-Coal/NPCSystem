"""
Tests for demo_game.game_end_checker (H1 multi-objective economy).

All tests are pure (no I/O, no network). They exercise:
- check_win: standing threshold + faction count (legacy path)
- check_lose: iron_legion control of guard barracks
- check_lose_bankrupt: bankruptcy predicate with None-safety
- check_lose_deadline: deadline predicate with won-already guard
- check_overreach: rival-faction floor detection
- check_win_multi: faction OR wealth OR quests OR treaty
- compute_grade: S/A/B/C banding
- _select_failure: priority ordering (legion > bankruptcy > deadline > overreach)
- evaluate_game_end: integrated outcome + precedence (lose beats win)
- detect_first_allied_faction: arc tracking
- ObjectiveState: new fields (win_path, failure_reason, total_gold, ticks_remaining, grade)
- ARC_WIN_SUBTITLES, WIN_PATH_SUBTITLES, LOSE_SUBTITLES: coverage checks
"""

from __future__ import annotations

import pytest

from demo_game.constants import (
    BANKRUPTCY_LOSE_THRESHOLD,
    DEADLINE_TICKS,
    DEMO_FACTIONS,
    FACTION_RIVALS,
    QUEST_CHAIN_WIN_COUNT,
    RIVAL_FLOOR,
    WEALTH_WIN_THRESHOLD,
    WIN_MIN_FACTIONS,
    WIN_QUEST_CHAIN_IDS,
    WIN_STANDING_THRESHOLD,
)
from demo_game.game_end_checker import (
    ARC_WIN_SUBTITLES,
    LOSE_SUBTITLES,
    LOSE_FACTION_ID,
    LOSE_LOCATION_ID,
    WIN_PATH_SUBTITLES,
    ObjectiveState,
    check_lose,
    check_lose_bankrupt,
    check_lose_deadline,
    check_overreach,
    check_win,
    check_win_multi,
    compute_grade,
    detect_first_allied_faction,
    evaluate_game_end,
)
from demo_game.world_objectives import TAVERN_OBJECTIVES, VILLAGE_OBJECTIVES

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_FACTIONS_AT_THRESHOLD: dict[str, int] = {f: WIN_STANDING_THRESHOLD for f in DEMO_FACTIONS}
_TWO_FACTIONS_AT_THRESHOLD: dict[str, int] = {
    "merchants_guild": WIN_STANDING_THRESHOLD,
    "city_guard": WIN_STANDING_THRESHOLD,
    "thieves_guild": 0,
}


# ---------------------------------------------------------------------------
# check_win (legacy faction path — must not regress)
# ---------------------------------------------------------------------------


def test_check_win_two_factions_at_threshold_returns_true():
    assert check_win(_TWO_FACTIONS_AT_THRESHOLD) is True


def test_check_win_all_three_factions_returns_true():
    standings = {f: WIN_STANDING_THRESHOLD + 10 for f in DEMO_FACTIONS}
    assert check_win(standings) is True


def test_check_win_one_faction_returns_false():
    assert check_win({"merchants_guild": 100, "city_guard": 0, "thieves_guild": 0}) is False


def test_check_win_below_threshold_returns_false():
    assert check_win({f: WIN_STANDING_THRESHOLD - 1 for f in DEMO_FACTIONS}) is False


def test_check_win_empty_standings_returns_false():
    assert check_win({}) is False


def test_check_win_unknown_factions_ignored():
    standings = {
        "merchants_guild": 100,
        "city_guard": 100,
        "iron_legion": 100,
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
# check_lose (legion path — must not regress)
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
# check_lose_bankrupt (H1.2)
# ---------------------------------------------------------------------------


def test_check_lose_bankrupt_none_returns_false():
    """None gold means unavailable — must never fire."""
    assert check_lose_bankrupt(None) is False


def test_check_lose_bankrupt_zero_returns_true():
    assert check_lose_bankrupt(BANKRUPTCY_LOSE_THRESHOLD) is True


def test_check_lose_bankrupt_positive_returns_false():
    assert check_lose_bankrupt(1) is False


def test_check_lose_bankrupt_large_positive_returns_false():
    assert check_lose_bankrupt(10_000) is False


def test_check_lose_bankrupt_negative_returns_true():
    """Negative gold (edge case) should also trigger bankruptcy."""
    assert check_lose_bankrupt(-1) is True


# ---------------------------------------------------------------------------
# check_lose_deadline (H1.4)
# ---------------------------------------------------------------------------


def test_check_lose_deadline_none_tick_returns_false():
    assert check_lose_deadline(None, False) is False


def test_check_lose_deadline_at_deadline_not_won():
    assert check_lose_deadline(DEADLINE_TICKS, False) is True


def test_check_lose_deadline_past_deadline_not_won():
    assert check_lose_deadline(DEADLINE_TICKS + 10, False) is True


def test_check_lose_deadline_at_deadline_already_won():
    """Photo-finish win: deadline must be skipped when player has won."""
    assert check_lose_deadline(DEADLINE_TICKS, True) is False


def test_check_lose_deadline_one_tick_before_deadline():
    assert check_lose_deadline(DEADLINE_TICKS - 1, False) is False


def test_check_lose_deadline_zero_ticks():
    assert check_lose_deadline(0, False) is False


# ---------------------------------------------------------------------------
# check_overreach (H1.3 — type-A gate)
# ---------------------------------------------------------------------------


def test_check_overreach_no_standings_returns_false():
    assert check_overreach({}) is False


def test_check_overreach_qualified_faction_rival_at_floor():
    """Qualified faction + rival exactly at RIVAL_FLOOR → no overreach (strictly <)."""
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "thieves_guild": RIVAL_FLOOR,
    }
    assert check_overreach(standings) is False


def test_check_overreach_qualified_faction_rival_below_floor():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "thieves_guild": RIVAL_FLOOR - 1,
    }
    assert check_overreach(standings) is True


def test_check_overreach_rival_floored_but_faction_not_qualified():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD - 1,
        "thieves_guild": RIVAL_FLOOR - 1,
    }
    assert check_overreach(standings) is False


def test_check_overreach_city_guard_rival_floored():
    standings = {
        "city_guard": WIN_STANDING_THRESHOLD,
        "thieves_guild": RIVAL_FLOOR - 1,
    }
    assert check_overreach(standings) is True


def test_check_overreach_all_positive_standings():
    standings = {f: WIN_STANDING_THRESHOLD for f in DEMO_FACTIONS}
    assert check_overreach(standings) is False


# ---------------------------------------------------------------------------
# check_win_multi (H1.1)
# ---------------------------------------------------------------------------


def test_check_win_multi_faction_path():
    assert check_win_multi(_TWO_FACTIONS_AT_THRESHOLD, 0, frozenset(), False) == "faction"


def test_check_win_multi_wealth_path():
    assert check_win_multi({}, WEALTH_WIN_THRESHOLD, frozenset(), False) == "wealth"


def test_check_win_multi_wealth_below_threshold_returns_none():
    assert check_win_multi({}, WEALTH_WIN_THRESHOLD - 1, frozenset(), False) is None


def test_check_win_multi_wealth_none_does_not_fire():
    assert check_win_multi({}, None, frozenset(), False) is None


def test_check_win_multi_quest_path():
    quest_ids = frozenset(list(WIN_QUEST_CHAIN_IDS)[:QUEST_CHAIN_WIN_COUNT])
    assert check_win_multi({}, 0, quest_ids, False) == "quests"


def test_check_win_multi_quest_path_too_few():
    quest_ids = frozenset(list(WIN_QUEST_CHAIN_IDS)[: QUEST_CHAIN_WIN_COUNT - 1])
    assert check_win_multi({}, 0, quest_ids, False) is None


def test_check_win_multi_treaty_path():
    assert check_win_multi({}, 0, frozenset(), True) == "treaty"


def test_check_win_multi_faction_beats_wealth():
    """Faction path has higher priority than wealth."""
    result = check_win_multi(_TWO_FACTIONS_AT_THRESHOLD, WEALTH_WIN_THRESHOLD, frozenset(), False)
    assert result == "faction"


def test_check_win_multi_wealth_beats_quests():
    """Wealth path has higher priority than quest-chain."""
    quest_ids = frozenset(list(WIN_QUEST_CHAIN_IDS)[:QUEST_CHAIN_WIN_COUNT])
    result = check_win_multi({}, WEALTH_WIN_THRESHOLD, quest_ids, False)
    assert result == "wealth"


def test_check_win_multi_no_path_returns_none():
    assert check_win_multi({}, 0, frozenset(), False) is None


# ---------------------------------------------------------------------------
# compute_grade (H1.6)
# ---------------------------------------------------------------------------


def test_compute_grade_s_all_factions_full_gold_time():
    """3 qualified factions + full gold + full ticks → S."""
    standings = {f: WIN_STANDING_THRESHOLD + 20 for f in DEMO_FACTIONS}
    grade = compute_grade(standings, WEALTH_WIN_THRESHOLD, DEADLINE_TICKS, frozenset())
    assert grade == "S"


def test_compute_grade_c_no_factions_no_gold_no_time():
    grade = compute_grade({}, 0, 0, frozenset())
    assert grade == "C"


def test_compute_grade_a_two_factions_some_gold():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "city_guard": WIN_STANDING_THRESHOLD,
        "thieves_guild": 0,
    }
    grade = compute_grade(standings, WEALTH_WIN_THRESHOLD // 2, DEADLINE_TICKS // 2, frozenset())
    # 40 (factions) + 10 (gold) + 10 (ticks) = 60 → B
    assert grade in ("A", "B", "C")


def test_compute_grade_with_none_gold_and_ticks():
    """None values should default to 0 without error."""
    grade = compute_grade(_ALL_FACTIONS_AT_THRESHOLD, None, None, frozenset())
    assert grade in ("S", "A", "B", "C")


# ---------------------------------------------------------------------------
# evaluate_game_end — integrated, no-regression
# ---------------------------------------------------------------------------


def test_evaluate_game_end_no_outcome():
    state = evaluate_game_end(
        reputation_records=[{"faction_id": "merchants_guild", "standing": 10}],
        iron_legion_controls=[],
    )
    assert state.outcome is None
    assert state.faction_standings["merchants_guild"] == 10


def test_evaluate_game_end_faction_win():
    records = [
        {"faction_id": "merchants_guild", "standing": 60},
        {"faction_id": "city_guard", "standing": 70},
    ]
    state = evaluate_game_end(records, iron_legion_controls=[])
    assert state.outcome == "win"
    assert state.win_path == "faction"


def test_evaluate_game_end_legion_lose():
    state = evaluate_game_end([], iron_legion_controls=[LOSE_LOCATION_ID])
    assert state.outcome == "lose"
    assert state.failure_reason == "legion"


def test_evaluate_game_end_lose_beats_win():
    """Lose condition dominates even when win condition is also satisfied."""
    records = [
        {"faction_id": "merchants_guild", "standing": 100},
        {"faction_id": "city_guard", "standing": 100},
    ]
    state = evaluate_game_end(records, iron_legion_controls=[LOSE_LOCATION_ID])
    assert state.outcome == "lose"
    assert state.failure_reason == "legion"


def test_evaluate_game_end_returns_objective_state_type():
    assert isinstance(evaluate_game_end([], []), ObjectiveState)


def test_evaluate_game_end_iron_legion_controls_stored():
    state = evaluate_game_end([], [LOSE_LOCATION_ID])
    assert LOSE_LOCATION_ID in state.iron_legion_controls


def test_evaluate_game_end_faction_standings_defaults_to_zero():
    state = evaluate_game_end([], [])
    for faction in DEMO_FACTIONS:
        assert state.faction_standings.get(faction, 0) == 0


# ---------------------------------------------------------------------------
# Bankruptcy lose via evaluate_game_end (H1.2 integration)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_bankruptcy_cold_start_does_not_lose():
    """Cold-start: gold=0, bankruptcy_armed=False → no lose."""
    state = evaluate_game_end([], [], total_gold=0, bankruptcy_armed=False)
    assert state.outcome is None


def test_evaluate_game_end_bankruptcy_armed_zero_gold_loses():
    state = evaluate_game_end([], [], total_gold=0, bankruptcy_armed=True)
    assert state.outcome == "lose"
    assert state.failure_reason == "bankruptcy"


def test_evaluate_game_end_bankruptcy_armed_positive_gold_no_lose():
    state = evaluate_game_end([], [], total_gold=1, bankruptcy_armed=True)
    assert state.outcome is None


def test_evaluate_game_end_bankruptcy_none_gold_no_lose():
    state = evaluate_game_end([], [], total_gold=None, bankruptcy_armed=True)
    assert state.outcome is None


# ---------------------------------------------------------------------------
# Deadline lose via evaluate_game_end (H1.4 integration)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_deadline_fires_when_past():
    # start_tick=0, current_tick=DEADLINE_TICKS → ticks_from_start == DEADLINE_TICKS
    state = evaluate_game_end(
        [], [], current_tick=DEADLINE_TICKS, start_tick=0
    )
    assert state.outcome == "lose"
    assert state.failure_reason == "deadline"


def test_evaluate_game_end_deadline_not_fired_before():
    state = evaluate_game_end(
        [], [], current_tick=DEADLINE_TICKS - 1, start_tick=0
    )
    assert state.outcome is None


def test_evaluate_game_end_deadline_skipped_when_already_won():
    """Win photo-finish: deadline must not override a simultaneous win."""
    records = [
        {"faction_id": "merchants_guild", "standing": 100},
        {"faction_id": "city_guard", "standing": 100},
    ]
    state = evaluate_game_end(
        records, [], current_tick=DEADLINE_TICKS + 5, start_tick=0
    )
    assert state.outcome == "win"
    assert state.failure_reason is None


def test_evaluate_game_end_ticks_remaining_computed():
    state = evaluate_game_end([], [], current_tick=10, start_tick=0)
    assert state.ticks_remaining == DEADLINE_TICKS - 10


def test_evaluate_game_end_ticks_remaining_none_when_no_tick():
    state = evaluate_game_end([], [])
    assert state.ticks_remaining is None


# ---------------------------------------------------------------------------
# Wealth win via evaluate_game_end (H1.1 / H1.2)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_wealth_win():
    state = evaluate_game_end([], [], total_gold=WEALTH_WIN_THRESHOLD)
    assert state.outcome == "win"
    assert state.win_path == "wealth"


def test_evaluate_game_end_wealth_just_below_threshold_no_win():
    state = evaluate_game_end([], [], total_gold=WEALTH_WIN_THRESHOLD - 1)
    assert state.outcome is None


# ---------------------------------------------------------------------------
# Quest-chain win via evaluate_game_end (H1.1)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_quest_chain_win():
    quest_ids = frozenset(list(WIN_QUEST_CHAIN_IDS)[:QUEST_CHAIN_WIN_COUNT])
    state = evaluate_game_end([], [], completed_quest_ids=quest_ids)
    assert state.outcome == "win"
    assert state.win_path == "quests"


def test_evaluate_game_end_quest_chain_too_few():
    quest_ids = frozenset(list(WIN_QUEST_CHAIN_IDS)[: QUEST_CHAIN_WIN_COUNT - 1])
    state = evaluate_game_end([], [], completed_quest_ids=quest_ids)
    assert state.outcome is None


# ---------------------------------------------------------------------------
# Treaty win via evaluate_game_end (H1.1)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_treaty_win():
    state = evaluate_game_end([], [], treaty_signed=True)
    assert state.outcome == "win"
    assert state.win_path == "treaty"


def test_evaluate_game_end_no_treaty_no_win():
    state = evaluate_game_end([], [], treaty_signed=False)
    assert state.outcome is None


# ---------------------------------------------------------------------------
# Failure priority ordering (legion > bankruptcy > deadline > overreach)
# ---------------------------------------------------------------------------


def test_failure_priority_legion_over_bankruptcy():
    state = evaluate_game_end(
        [],
        [LOSE_LOCATION_ID],
        total_gold=0,
        bankruptcy_armed=True,
    )
    assert state.failure_reason == "legion"


def test_failure_priority_bankruptcy_over_deadline():
    state = evaluate_game_end(
        [],
        [],
        total_gold=0,
        bankruptcy_armed=True,
        current_tick=DEADLINE_TICKS,
        start_tick=0,
    )
    assert state.failure_reason == "bankruptcy"


# ---------------------------------------------------------------------------
# Per-world objectives (H2.7 / DEMO-D2-08) — village + tavern eval worlds
# ---------------------------------------------------------------------------


def test_check_win_uses_village_factions():
    """Allying both village factions wins via the village objectives."""
    standings = {
        "vw_village_council": WIN_STANDING_THRESHOLD,
        "vw_farmers": WIN_STANDING_THRESHOLD,
    }
    assert check_win(standings, VILLAGE_OBJECTIVES) is True


def test_check_win_demo_factions_ignored_in_village_world():
    """Demo factions do not count toward the village win."""
    standings = {f: WIN_STANDING_THRESHOLD for f in DEMO_FACTIONS}
    assert check_win(standings, VILLAGE_OBJECTIVES) is False


def test_village_world_is_winnable_via_faction_path():
    records = [
        {"faction_id": "vw_village_council", "standing": 60},
        {"faction_id": "vw_farmers", "standing": 55},
    ]
    state = evaluate_game_end(records, [], objectives=VILLAGE_OBJECTIVES)
    assert state.outcome == "win"
    assert state.win_path == "faction"


def test_village_world_has_no_legion_lose():
    """Village world has no antagonist — the demo lose location never loses it."""
    state = evaluate_game_end(
        [], [LOSE_LOCATION_ID], objectives=VILLAGE_OBJECTIVES
    )
    assert state.outcome is None


def test_village_world_quest_chain_disabled():
    """Empty win_quest_chain_ids means completed quests cannot win the village world."""
    state = evaluate_game_end(
        [],
        [],
        completed_quest_ids=WIN_QUEST_CHAIN_IDS,
        objectives=VILLAGE_OBJECTIVES,
    )
    assert state.outcome is None


def test_village_world_has_no_overreach():
    """No faction_rivals → overreach never blocks a village win."""
    standings = {
        "vw_village_council": WIN_STANDING_THRESHOLD,
        "vw_farmers": WIN_STANDING_THRESHOLD,
    }
    assert check_overreach(standings, VILLAGE_OBJECTIVES) is False


def test_tavern_world_is_winnable_via_faction_path():
    records = [
        {"faction_id": "tw_merchants", "standing": 80},
        {"faction_id": "tw_innkeepers", "standing": 80},
    ]
    state = evaluate_game_end(records, [], objectives=TAVERN_OBJECTIVES)
    assert state.outcome == "win"
    assert state.win_path == "faction"


def test_tavern_world_wealth_path_still_works():
    """Wealth is world-agnostic — the tavern world wins on gold too."""
    state = evaluate_game_end(
        [], [], total_gold=WEALTH_WIN_THRESHOLD, objectives=TAVERN_OBJECTIVES
    )
    assert state.outcome == "win"
    assert state.win_path == "wealth"


def test_detect_first_allied_faction_village_world():
    standings = {"vw_village_council": 70, "vw_farmers": 50}
    assert (
        detect_first_allied_faction(standings, VILLAGE_OBJECTIVES)
        == "vw_village_council"
    )


def test_demo_objectives_remain_default_for_evaluate():
    """Omitting objectives still evaluates the demo world (no regression)."""
    records = [
        {"faction_id": "merchants_guild", "standing": 60},
        {"faction_id": "city_guard", "standing": 70},
    ]
    state = evaluate_game_end(records, [])
    assert state.outcome == "win"
    assert state.win_path == "faction"


def test_failure_priority_deadline_over_overreach():
    standings = {
        "merchants_guild": WIN_STANDING_THRESHOLD,
        "thieves_guild": RIVAL_FLOOR - 1,
    }
    records = [
        {"faction_id": "merchants_guild", "standing": WIN_STANDING_THRESHOLD},
        {"faction_id": "thieves_guild", "standing": RIVAL_FLOOR - 1},
    ]
    state = evaluate_game_end(
        records,
        [],
        current_tick=DEADLINE_TICKS,
        start_tick=0,
    )
    assert state.failure_reason == "deadline"


# ---------------------------------------------------------------------------
# Grade on win (H1.6 integration)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_win_has_grade():
    records = [
        {"faction_id": "merchants_guild", "standing": 100},
        {"faction_id": "city_guard", "standing": 100},
    ]
    state = evaluate_game_end(records, [])
    assert state.outcome == "win"
    assert state.grade in ("S", "A", "B", "C")


def test_evaluate_game_end_lose_has_no_grade():
    state = evaluate_game_end([], [LOSE_LOCATION_ID])
    assert state.grade is None


def test_evaluate_game_end_in_progress_has_no_grade():
    state = evaluate_game_end([], [])
    assert state.grade is None


# ---------------------------------------------------------------------------
# total_gold stored in ObjectiveState
# ---------------------------------------------------------------------------


def test_evaluate_game_end_total_gold_stored():
    state = evaluate_game_end([], [], total_gold=250)
    assert state.total_gold == 250


def test_evaluate_game_end_total_gold_none_stored():
    state = evaluate_game_end([], [])
    assert state.total_gold is None


# ---------------------------------------------------------------------------
# detect_first_allied_faction
# ---------------------------------------------------------------------------


def test_detect_first_allied_empty_standings_returns_none():
    assert detect_first_allied_faction({}) is None


def test_detect_first_allied_no_faction_at_threshold_returns_none():
    assert detect_first_allied_faction({f: WIN_STANDING_THRESHOLD - 1 for f in DEMO_FACTIONS}) is None


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
# ARC_WIN_SUBTITLES (backward compat)
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
# WIN_PATH_SUBTITLES + LOSE_SUBTITLES (H1.5)
# ---------------------------------------------------------------------------


def test_win_path_subtitles_covers_all_paths():
    for path in ("faction", "wealth", "quests", "treaty"):
        assert path in WIN_PATH_SUBTITLES, f"Missing WIN_PATH_SUBTITLES entry for {path}"


def test_win_path_subtitles_values_non_empty():
    for key, value in WIN_PATH_SUBTITLES.items():
        assert isinstance(value, str) and value.strip()


def test_lose_subtitles_covers_all_failure_reasons():
    for reason in ("legion", "bankruptcy", "deadline", "overreach"):
        assert reason in LOSE_SUBTITLES, f"Missing LOSE_SUBTITLES entry for {reason}"


def test_lose_subtitles_values_non_empty():
    for key, value in LOSE_SUBTITLES.items():
        assert isinstance(value, str) and value.strip()


# ---------------------------------------------------------------------------
# arc_faction field (backward compat)
# ---------------------------------------------------------------------------


def test_evaluate_game_end_arc_faction_stored():
    records = [{"faction_id": "merchants_guild", "standing": 60}]
    state = evaluate_game_end(records, [], arc_faction="merchants_guild")
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
        [LOSE_LOCATION_ID],
        arc_faction="city_guard",
    )
    assert state.outcome == "lose"
    assert state.arc_faction == "city_guard"


# ---------------------------------------------------------------------------
# FACTION_RIVALS / RIVAL_FLOOR constants sanity
# ---------------------------------------------------------------------------


def test_faction_rivals_constant_has_entries():
    assert len(FACTION_RIVALS) > 0


def test_rival_floor_is_negative():
    assert RIVAL_FLOOR < 0


def test_win_quest_chain_ids_has_enough_entries():
    assert len(WIN_QUEST_CHAIN_IDS) >= QUEST_CHAIN_WIN_COUNT
