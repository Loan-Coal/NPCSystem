"""
Module: world_objectives
Layer: demo_game
Purpose: Per-world win/lose objective bundles (H2.7 / DEMO-D2-08). Decouples the
         game_end_checker from a single hardcoded world so the demo, village, and
         tavern seeded worlds are each pickable and winnable.
Dependencies: dataclasses, demo_game.constants
Used by: demo_game.game_end_checker, demo_game.game_end_poller, demo_game.ui.game_window

game_end_checker.py was originally hardcoded to the demo world's factions, lose
location, and antagonist. WorldObjectives bundles every world-specific win/lose
tunable so the Village and Tavern eval worlds (which have different factions and no
military antagonist) become pickable and winnable. The demo world's values are
unchanged — DEMO_OBJECTIVES is the default everywhere the evaluator is called.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

# Demo world's military antagonist + the location whose capture loses the game.
# Iron Legion armies are seeded at loc_guard_barracks (see seed.py _ARMIES);
# military_battle_service writes CONTROLS only at the battle location.
DEMO_LOSE_LOCATION_ID: str = "loc_guard_barracks"
DEMO_LOSE_FACTION_ID: str = "iron_legion"

# World ids used to select a WorldObjectives bundle from WORLD_OBJECTIVES.
DEMO_WORLD_ID: str = "demo"
VILLAGE_WORLD_ID: str = "village"
TAVERN_WORLD_ID: str = "tavern"

# Eval worlds share the demo's economy/deadline scale; only their factions and
# (absence of an) antagonist differ. Named here so the bundles read declaratively.
VILLAGE_FACTIONS: tuple[str, ...] = ("vw_village_council", "vw_farmers")
TAVERN_FACTIONS: tuple[str, ...] = ("tw_merchants", "tw_innkeepers")
# Eval worlds need fewer allied factions to win (they only have two factions).
EVAL_WIN_MIN_FACTIONS: int = 2


@dataclass(frozen=True)
class WorldObjectives:
    """Per-world win/lose tuning bundle consumed by game_end_checker.

    Every value here was previously a module-level constant hardcoded to the
    demo world. Bundling them lets the same pure evaluator drive any seeded
    world. The demo bundle (DEMO_OBJECTIVES) reproduces the original constants
    exactly, so existing behaviour is unchanged.

    Attributes:
        factions: Win-eligible faction IDs for the faction-standing win path.
        win_standing_threshold: Minimum standing to count a faction as allied.
        win_min_factions: Allied factions required for the faction win path.
        lose_location_id: Location whose capture by lose_faction_id loses the
            game; empty string disables the legion lose path (no antagonist).
        lose_faction_id: Antagonist faction polled for CONTROLS edges; empty
            string disables the legion lose path.
        wealth_win_threshold: Gold balance that triggers the wealth win path.
        bankruptcy_lose_threshold: Gold at or below which bankruptcy loses
            (armed only after gold was once positive).
        quest_chain_win_count: Completed quest-chain quests required to win.
        win_quest_chain_ids: Quest IDs counting toward the quest-chain path;
            empty frozenset disables the quest-chain win path.
        deadline_ticks: Ticks from the start latch before the deadline lose.
        rival_floor: Standing below which a rival faction is "floored".
        faction_rivals: Map of qualified faction → rival used for overreach;
            empty map disables the overreach win-blocker.
    """

    factions: tuple[str, ...]
    win_standing_threshold: int
    win_min_factions: int
    lose_location_id: str
    lose_faction_id: str
    wealth_win_threshold: int
    bankruptcy_lose_threshold: int
    quest_chain_win_count: int
    win_quest_chain_ids: frozenset[str]
    deadline_ticks: int
    rival_floor: int
    faction_rivals: dict[str, str] = field(default_factory=dict)


def _eval_world_objectives(factions: tuple[str, ...]) -> WorldObjectives:
    """Build a two-faction eval-world bundle with no antagonist or quest chain.

    Args:
        factions: The world's win-eligible faction IDs.

    Returns:
        A WorldObjectives winnable by allying both factions (or by wealth).
    """
    return WorldObjectives(
        factions=factions,
        win_standing_threshold=WIN_STANDING_THRESHOLD,
        win_min_factions=EVAL_WIN_MIN_FACTIONS,
        lose_location_id="",
        lose_faction_id="",
        wealth_win_threshold=WEALTH_WIN_THRESHOLD,
        bankruptcy_lose_threshold=BANKRUPTCY_LOSE_THRESHOLD,
        quest_chain_win_count=QUEST_CHAIN_WIN_COUNT,
        win_quest_chain_ids=frozenset(),
        deadline_ticks=DEADLINE_TICKS,
        rival_floor=RIVAL_FLOOR,
    )


# Demo world — reproduces the original hardcoded game_end_checker constants.
DEMO_OBJECTIVES: WorldObjectives = WorldObjectives(
    factions=DEMO_FACTIONS,
    win_standing_threshold=WIN_STANDING_THRESHOLD,
    win_min_factions=WIN_MIN_FACTIONS,
    lose_location_id=DEMO_LOSE_LOCATION_ID,
    lose_faction_id=DEMO_LOSE_FACTION_ID,
    wealth_win_threshold=WEALTH_WIN_THRESHOLD,
    bankruptcy_lose_threshold=BANKRUPTCY_LOSE_THRESHOLD,
    quest_chain_win_count=QUEST_CHAIN_WIN_COUNT,
    win_quest_chain_ids=WIN_QUEST_CHAIN_IDS,
    deadline_ticks=DEADLINE_TICKS,
    rival_floor=RIVAL_FLOOR,
    faction_rivals=FACTION_RIVALS,
)

# Village eval world (vw_ prefix): two civic/agrarian factions, no military
# antagonist and no quest chain — win by allying both factions (or by wealth).
VILLAGE_OBJECTIVES: WorldObjectives = _eval_world_objectives(VILLAGE_FACTIONS)

# Tavern eval world (tw_ prefix): two mercantile/civic factions, no antagonist
# and no quest chain — win by allying both factions (or by wealth).
TAVERN_OBJECTIVES: WorldObjectives = _eval_world_objectives(TAVERN_FACTIONS)

# Registry: world id → objectives. game_window selects by the active world.
WORLD_OBJECTIVES: dict[str, WorldObjectives] = {
    DEMO_WORLD_ID: DEMO_OBJECTIVES,
    VILLAGE_WORLD_ID: VILLAGE_OBJECTIVES,
    TAVERN_WORLD_ID: TAVERN_OBJECTIVES,
}
