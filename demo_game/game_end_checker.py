"""
Module: game_end_checker
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Pure win/lose condition evaluator for H1 multi-objective economy.
         Supports faction, wealth, quest-chain, and treaty win paths.
         Supports legion, bankruptcy, deadline, and overreach failure reasons.
         No I/O: accepts pre-fetched data and returns an ObjectiveState.
Dependencies: demo_game.constants
Used by: demo_game.game_end_poller, demo_game.ui.game_window

300-LINE WAIVER (DEC-108): this is one cohesive pure win/lose evaluator — the four win
predicates, four failure predicates, grade scoring, the priority `_select_failure` chain,
and the ObjectiveState/subtitle maps all share one concern (deciding the game outcome) and
move together. Splitting the predicates into a sibling module would scatter a single
decision across files for no cohesion gain. `evaluate_game_end` stays ≤40 lines (logic
extracted into the named predicate/helpers). See DECISIONS.md DEC-108.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from demo_game.constants import (
    BANKRUPTCY_LOSE_THRESHOLD,
    DEADLINE_TICKS,
    DEMO_FACTIONS,
    FACTION_RIVALS,
    GRADE_A_MIN_SCORE,
    GRADE_B_MIN_SCORE,
    GRADE_S_MIN_SCORE,
    QUEST_CHAIN_WIN_COUNT,
    RIVAL_FLOOR,
    WEALTH_WIN_THRESHOLD,
    WIN_MIN_FACTIONS,
    WIN_QUEST_CHAIN_IDS,
    WIN_STANDING_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Lose condition constants.
# Iron Legion armies are seeded at loc_guard_barracks (see seed.py _ARMIES);
# military_battle_service writes CONTROLS only at the battle location.
LOSE_LOCATION_ID: str = "loc_guard_barracks"
LOSE_FACTION_ID: str = "iron_legion"

# Arc-specific win ending subtitles keyed by first-allied faction (None = generic fallback).
ARC_WIN_SUBTITLES: dict[str | None, str] = {
    "merchants_guild": (
        "With the merchants' wealth behind you, commerce and coin turned the tide."
    ),
    "city_guard": (
        "The city guard's steel held the line. The Iron Legion broke against their shields."
    ),
    "thieves_guild": (
        "The shadow network's reach proved unstoppable. The Iron Legion never saw it coming."
    ),
    None: "You earned the trust of two factions. The town is saved.",
}

# Win-path subtitles keyed by win_path value.
WIN_PATH_SUBTITLES: dict[str, str] = {
    "faction": ARC_WIN_SUBTITLES[None],
    "wealth": "Coin conquered all — your coffers secured the town's salvation.",
    "quests": "Your deeds spoke louder than words. The quest chain is complete.",
    "treaty": "A signed peace sealed the fate of the Iron Legion.",
}

# Failure subtitles keyed by failure_reason value.
LOSE_SUBTITLES: dict[str, str] = {
    "legion": "The Iron Legion has taken the market square. All is lost.",
    "bankruptcy": "Your coffers are empty. Without gold, the town could not be saved.",
    "deadline": "Time ran out. The Iron Legion marched before you could rally the town.",
    "overreach": "Your alliances fractured under the weight of your ambitions.",
}

# Score contribution weights for compute_grade.
_GRADE_FACTION_MAX_SCORE: int = 60   # max score from faction standings
_GRADE_GOLD_MAX_SCORE: int = 20      # max score from gold (capped at WEALTH_WIN_THRESHOLD)
_GRADE_TICKS_MAX_SCORE: int = 20     # max score from ticks remaining (capped at DEADLINE_TICKS)


# ---------------------------------------------------------------------------
# ObjectiveState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObjectiveState:
    """Snapshot of the current win/lose objective state.

    Attributes:
        faction_standings: Map of faction_id → standing value for the player.
        iron_legion_controls: Location IDs currently controlled by iron_legion.
        outcome: "win", "lose", or None when the game is still in progress.
        arc_faction: The first demo faction the player allied with (first to reach
            WIN_STANDING_THRESHOLD), or None if not yet determined.
        win_path: Which win condition fired ("faction", "wealth", "quests", "treaty"),
            or None if the game is not yet won.
        failure_reason: Which lose condition fired ("legion", "bankruptcy", "deadline",
            "overreach"), or None if the game is not lost.
        total_gold: Player gold balance at evaluation time, or None if unavailable.
        ticks_remaining: Ticks until the deadline (may be negative if past deadline),
            or None if the clock has not been polled yet.
        grade: S/A/B/C awarded on win, or None on lose/in-progress.
    """

    faction_standings: dict[str, int]
    iron_legion_controls: list[str]
    outcome: Literal["win", "lose"] | None
    arc_faction: str | None = None
    win_path: Literal["faction", "wealth", "quests", "treaty"] | None = None
    failure_reason: Literal["legion", "bankruptcy", "deadline", "overreach"] | None = None
    total_gold: int | None = None
    ticks_remaining: int | None = None
    grade: Literal["S", "A", "B", "C"] | None = None


# ---------------------------------------------------------------------------
# Individual predicates (pure, small, testable)
# ---------------------------------------------------------------------------


def detect_first_allied_faction(faction_standings: dict[str, int]) -> str | None:
    """Return the demo faction with the highest standing at or above WIN_STANDING_THRESHOLD.

    Args:
        faction_standings: Map of faction_id → current standing value.

    Returns:
        Faction ID of the leading qualified faction, or None if none qualify.
    """
    qualified = [
        (faction_standings[f], f)
        for f in DEMO_FACTIONS
        if faction_standings.get(f, 0) >= WIN_STANDING_THRESHOLD
    ]
    if not qualified:
        return None
    return max(qualified)[1]


def check_win(faction_standings: dict[str, int]) -> bool:
    """Return True if ≥ WIN_MIN_FACTIONS demo factions are at or above WIN_STANDING_THRESHOLD.

    Args:
        faction_standings: Map of faction_id → current standing value.

    Returns:
        True if the faction win condition is satisfied.
    """
    qualified = sum(
        1
        for faction in DEMO_FACTIONS
        if faction_standings.get(faction, 0) >= WIN_STANDING_THRESHOLD
    )
    return qualified >= WIN_MIN_FACTIONS


def check_lose(iron_legion_controls: list[str]) -> bool:
    """Return True if the iron_legion has taken LOSE_LOCATION_ID.

    Args:
        iron_legion_controls: Location IDs currently under iron_legion control.

    Returns:
        True if the legion lose condition is satisfied.
    """
    return LOSE_LOCATION_ID in iron_legion_controls


def check_lose_bankrupt(total_gold: int | None) -> bool:
    """Return True if the player's gold has hit BANKRUPTCY_LOSE_THRESHOLD.

    Only ever fires when the caller has confirmed gold was once positive
    (the _seen_positive_gold latch in game_end_poller).

    Args:
        total_gold: Current gold balance; None means unavailable (not fired).

    Returns:
        True if gold is available and ≤ BANKRUPTCY_LOSE_THRESHOLD.
    """
    return total_gold is not None and total_gold <= BANKRUPTCY_LOSE_THRESHOLD


def check_lose_deadline(current_tick: int | None, won: bool) -> bool:
    """Return True if the deadline has passed and the player has not yet won.

    Args:
        current_tick: Ticks elapsed from the game-start latch; None = not yet set.
        won: Whether a win condition has already been met (deadline skipped if so).

    Returns:
        True if the deadline is exceeded and no win path was satisfied.
    """
    if won or current_tick is None:
        return False
    return current_tick >= DEADLINE_TICKS


def check_overreach(standings: dict[str, int]) -> bool:
    """Return True if any qualified faction has a rival standing below RIVAL_FLOOR.

    Overreach fires when the player allies a faction but has alienated its rival
    so severely that the victory is tainted.

    Args:
        standings: Map of faction_id → current standing value.

    Returns:
        True if any FACTION_RIVALS pair is in overreach state.
    """
    for faction, rival in FACTION_RIVALS.items():
        faction_qualified = standings.get(faction, 0) >= WIN_STANDING_THRESHOLD
        rival_floored = standings.get(rival, 0) < RIVAL_FLOOR
        if faction_qualified and rival_floored:
            return True
    return False


def check_win_multi(
    standings: dict[str, int],
    total_gold: int | None,
    completed_quest_ids: frozenset[str],
    treaty_signed: bool,
) -> Literal["faction", "wealth", "quests", "treaty"] | None:
    """Return the first win path that is satisfied, or None.

    Priority order: faction → wealth → quests → treaty.

    Args:
        standings: Map of faction_id → current standing value.
        total_gold: Player gold balance, or None if unavailable.
        completed_quest_ids: Set of quest IDs with status "completed".
        treaty_signed: Whether at least one active treaty exists for the player.

    Returns:
        Win-path label if any path is satisfied, else None.
    """
    if check_win(standings):
        return "faction"
    if total_gold is not None and total_gold >= WEALTH_WIN_THRESHOLD:
        return "wealth"
    completed_chain = completed_quest_ids & WIN_QUEST_CHAIN_IDS
    if len(completed_chain) >= QUEST_CHAIN_WIN_COUNT:
        return "quests"
    if treaty_signed:
        return "treaty"
    return None


def _select_failure(
    standings: dict[str, int],
    iron_legion_controls: list[str],
    total_gold: int | None,
    ticks_from_start: int | None,
    won: bool,
) -> Literal["legion", "bankruptcy", "deadline", "overreach"] | None:
    """Return the highest-priority failure reason, or None.

    Priority: legion > bankruptcy > deadline > overreach.
    Overreach acts as a win-blocker here when the faction path would have fired —
    it prevents the win rather than forcing a separate lose, per DEMO-D3-03 type-A.

    Args:
        standings: Map of faction_id → current standing value.
        iron_legion_controls: Location IDs under iron_legion control.
        total_gold: Player gold balance (bankruptcy-armed by caller).
        ticks_from_start: Ticks elapsed since game start latch; None = unchecked.
        won: Whether a win path was satisfied (deadline skipped if True).

    Returns:
        Failure reason string, or None if no failure condition fires.
    """
    if check_lose(iron_legion_controls):
        return "legion"
    if check_lose_bankrupt(total_gold):
        return "bankruptcy"
    if check_lose_deadline(ticks_from_start, won):
        return "deadline"
    if check_overreach(standings):
        return "overreach"
    return None


def compute_grade(
    standings: dict[str, int],
    total_gold: int | None,
    ticks_remaining: int | None,
    completed_quest_ids: frozenset[str],
) -> Literal["S", "A", "B", "C"]:
    """Compute a grade S/A/B/C for a win outcome.

    Score = faction_score + gold_score + ticks_score (max 100).
    Grade bands use GRADE_*_MIN_SCORE constants from constants.py.

    Args:
        standings: Map of faction_id → current standing value.
        total_gold: Final gold balance (None treated as 0).
        ticks_remaining: Ticks left before deadline (None treated as 0).
        completed_quest_ids: Set of completed quest IDs.

    Returns:
        Grade letter.
    """
    faction_score = _faction_score(standings)
    gold_score = _gold_score(total_gold)
    ticks_score = _ticks_score(ticks_remaining)
    total = faction_score + gold_score + ticks_score
    if total >= GRADE_S_MIN_SCORE:
        return "S"
    if total >= GRADE_A_MIN_SCORE:
        return "A"
    if total >= GRADE_B_MIN_SCORE:
        return "B"
    return "C"


def _faction_score(standings: dict[str, int]) -> int:
    """Compute faction sub-score (0..60) from standings."""
    qualified = sum(
        1 for f in DEMO_FACTIONS if standings.get(f, 0) >= WIN_STANDING_THRESHOLD
    )
    # 3 factions → 60, 2 → 40, 1 → 20, 0 → 0
    return min(qualified * 20, _GRADE_FACTION_MAX_SCORE)


def _gold_score(total_gold: int | None) -> int:
    """Compute gold sub-score (0..20) capped at WEALTH_WIN_THRESHOLD."""
    gold = total_gold or 0
    ratio = min(gold / WEALTH_WIN_THRESHOLD, 1.0)
    return int(ratio * _GRADE_GOLD_MAX_SCORE)


def _ticks_score(ticks_remaining: int | None) -> int:
    """Compute time sub-score (0..20) — more ticks left = better."""
    remaining = max(ticks_remaining or 0, 0)
    ratio = min(remaining / DEADLINE_TICKS, 1.0)
    return int(ratio * _GRADE_TICKS_MAX_SCORE)


# ---------------------------------------------------------------------------
# Top-level evaluator
# ---------------------------------------------------------------------------


def evaluate_game_end(
    reputation_records: list[dict],
    iron_legion_controls: list[str],
    *,
    arc_faction: str | None = None,
    total_gold: int | None = None,
    current_tick: int | None = None,
    start_tick: int | None = None,
    completed_quest_ids: frozenset[str] = frozenset(),
    treaty_signed: bool = False,
    bankruptcy_armed: bool = False,
) -> ObjectiveState:
    """Evaluate all win/lose conditions and return a complete ObjectiveState.

    Evaluation order (per DEMO-D3-05 priority):
    1. Compute win_path (faction/wealth/quests/treaty).
    2. Compute failure (legion > bankruptcy > deadline > overreach).
       Lose beats win when both fire simultaneously.
    3. Assign outcome and grade.

    Note: deadline-lose is skipped when a win path has already fired (won=True),
    so a photo-finish win is not retroactively reversed by the clock.  All other
    lose conditions (legion, bankruptcy, overreach) override win.

    Args:
        reputation_records: List of dicts from GET /v1/graph/characters/{id}/reputation.
                            Each dict must contain "faction_id" and "standing" keys.
        iron_legion_controls: Location IDs from CONTROLS edges where src=iron_legion.
        arc_faction: First demo faction the player allied with (S7.3 arc tracking).
        total_gold: Player gold balance; None if not yet polled.
        current_tick: Absolute clock tick; None if not yet polled.
        start_tick: Absolute clock tick when the first poll completed; used to
                    compute ticks_from_start.  None before latch is set.
        completed_quest_ids: Frozenset of quest IDs with status "completed".
        treaty_signed: Whether at least one active treaty exists for the player.
        bankruptcy_armed: Whether gold was once > 0 (latch from game_end_poller).

    Returns:
        ObjectiveState with all fields populated.
    """
    standings: dict[str, int] = {
        rec["faction_id"]: int(rec.get("standing", 0))
        for rec in reputation_records
    }

    ticks_from_start = _compute_ticks_from_start(current_tick, start_tick)
    ticks_remaining = _compute_ticks_remaining(ticks_from_start)
    gold_for_bankruptcy = total_gold if bankruptcy_armed else None

    win_path = check_win_multi(standings, total_gold, completed_quest_ids, treaty_signed)
    won = win_path is not None
    failure = _select_failure(
        standings, iron_legion_controls, gold_for_bankruptcy, ticks_from_start, won
    )
    outcome: Literal["win", "lose"] | None = (
        "lose" if failure else ("win" if won else None)
    )
    grade = compute_grade(standings, total_gold, ticks_remaining, completed_quest_ids) if outcome == "win" else None
    actual_win_path = win_path if outcome == "win" else None

    return ObjectiveState(
        faction_standings=standings,
        iron_legion_controls=list(iron_legion_controls),
        outcome=outcome,
        arc_faction=arc_faction,
        win_path=actual_win_path,
        failure_reason=failure,
        total_gold=total_gold,
        ticks_remaining=ticks_remaining,
        grade=grade,
    )


def _compute_ticks_from_start(
    current_tick: int | None, start_tick: int | None
) -> int | None:
    """Compute elapsed ticks since the game-start latch.

    Returns None if either tick is not yet available.

    Args:
        current_tick: Absolute clock tick from the server.
        start_tick: Absolute clock tick latched on first poll.

    Returns:
        Ticks elapsed, or None.
    """
    if current_tick is None or start_tick is None:
        return None
    return current_tick - start_tick


def _compute_ticks_remaining(ticks_from_start: int | None) -> int | None:
    """Compute ticks remaining until deadline.

    Args:
        ticks_from_start: Elapsed ticks since latch, or None.

    Returns:
        DEADLINE_TICKS - elapsed, or None.
    """
    if ticks_from_start is None:
        return None
    return DEADLINE_TICKS - ticks_from_start
