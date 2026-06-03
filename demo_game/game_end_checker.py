"""
Module: game_end_checker
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Pure win/lose condition evaluator for S7.1 game objectives.
         Also tracks the first allied faction (S7.3 arc tracking).
         No I/O: accepts pre-fetched API data and returns an ObjectiveState.
Dependencies: none
Used by: demo_game.game_end_poller, demo_game.ui.game_window
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Win condition constants.
WIN_STANDING_THRESHOLD: int = 50
WIN_MIN_FACTIONS: int = 2

# The three factions the player can ally with.
DEMO_FACTIONS: tuple[str, ...] = ("merchants_guild", "city_guard", "thieves_guild")

# Lose condition constants.
LOSE_LOCATION_ID: str = "loc_market_square"
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


@dataclass(frozen=True)
class ObjectiveState:
    """Snapshot of the current win/lose objective state.

    Attributes:
        faction_standings: Map of faction_id → standing value for the player.
        iron_legion_controls: Location IDs currently controlled by iron_legion.
        outcome: "win", "lose", or None when the game is still in progress.
        arc_faction: The first demo faction the player allied with (first to reach
            WIN_STANDING_THRESHOLD), or None if not yet determined.
    """

    faction_standings: dict[str, int]
    iron_legion_controls: list[str]
    outcome: Literal["win", "lose"] | None
    arc_faction: str | None = None


def detect_first_allied_faction(faction_standings: dict[str, int]) -> str | None:
    """Return the demo faction with the highest standing at or above WIN_STANDING_THRESHOLD.

    Used as a tiebreaker when multiple factions qualify simultaneously: the most
    invested-in faction (highest current standing) is treated as the "first" ally.
    Returns None if no demo faction has reached the threshold yet.

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
    """Return True if the player meets the win condition.

    Win condition: standing ≥ WIN_STANDING_THRESHOLD with ≥ WIN_MIN_FACTIONS
    of the three demo factions.

    Args:
        faction_standings: Map of faction_id → current standing value.

    Returns:
        True if win condition is satisfied.
    """
    qualified = sum(
        1
        for faction in DEMO_FACTIONS
        if faction_standings.get(faction, 0) >= WIN_STANDING_THRESHOLD
    )
    return qualified >= WIN_MIN_FACTIONS


def check_lose(iron_legion_controls: list[str]) -> bool:
    """Return True if the iron_legion has taken the market square.

    Lose condition: LOSE_LOCATION_ID appears in iron_legion_controls.

    Args:
        iron_legion_controls: Location IDs currently under iron_legion control.

    Returns:
        True if lose condition is satisfied.
    """
    return LOSE_LOCATION_ID in iron_legion_controls


def evaluate_game_end(
    reputation_records: list[dict],
    iron_legion_controls: list[str],
    *,
    arc_faction: str | None = None,
) -> ObjectiveState:
    """Evaluate the current win/lose conditions from raw API data.

    Lose is checked before win so that simultaneous satisfaction (edge case)
    resolves to "lose" — the dramatic outcome for the demo narrative.

    Args:
        reputation_records: List of dicts from GET /v1/graph/characters/{id}/reputation.
                            Each dict must contain "faction_id" and "standing" keys.
        iron_legion_controls: Location IDs from CONTROLS edges where src=iron_legion.
        arc_faction: First demo faction the player allied with (S7.3 arc tracking).
                     Caller is responsible for freezing this once set.

    Returns:
        ObjectiveState with faction_standings, iron_legion_controls, outcome, and arc_faction.
    """
    standings: dict[str, int] = {
        rec["faction_id"]: int(rec.get("standing", 0))
        for rec in reputation_records
    }

    outcome: Literal["win", "lose"] | None = None
    if check_lose(iron_legion_controls):
        outcome = "lose"
    elif check_win(standings):
        outcome = "win"

    return ObjectiveState(
        faction_standings=standings,
        iron_legion_controls=list(iron_legion_controls),
        outcome=outcome,
        arc_faction=arc_faction,
    )
