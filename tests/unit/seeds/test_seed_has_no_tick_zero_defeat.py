"""
Module: test_seed_has_no_tick_zero_defeat
Layer: tests/unit/seeds
Purpose: Guards that the demo seed does not stage a tick-0 defeat.

Two invariants are checked against the raw Python seed data (no I/O, no Neo4j):
  1. The DEMO_LOSE_FACTION_ID army does not occupy DEMO_LOSE_LOCATION_ID at tick 0.
  2. No two armies from different factions share a location at tick 0.

Both conditions must hold or the military engine (while it existed) would resolve a
battle on tick 1, handing iron_legion a CONTROLS edge at loc_guard_barracks before
any player action. T1.2 deletes the military engine and moves army_iron_legion to
loc_north_gate so the seed itself cannot stage an automatic conquest.
"""

from __future__ import annotations

from demo_game.seeds.seed import _ARMIES, _ARMY_OCCUPIES
from demo_game.world_objectives import DEMO_LOSE_FACTION_ID, DEMO_LOSE_LOCATION_ID


def _army_to_faction() -> dict[str, str]:
    return {army_id: faction_id for army_id, faction_id, *_ in _ARMIES}


def _tick_zero_occupancies() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for army_id, loc_id, since in _ARMY_OCCUPIES:
        if since == 0:
            result.setdefault(loc_id, []).append(army_id)
    return result


def test_lose_faction_army_not_at_lose_location_at_tick_zero() -> None:
    """The lose-faction army must not occupy DEMO_LOSE_LOCATION_ID at tick 0.

    A CONTROLS edge at the barracks is written by military_battle_service when opposing
    armies meet there; the game_end_checker fires the lose condition when iron_legion
    holds that CONTROLS edge. This guard ensures the seed does not pre-stage the outcome.
    """
    army_to_faction = _army_to_faction()
    occupancies = _tick_zero_occupancies()
    armies_at_lose_location = occupancies.get(DEMO_LOSE_LOCATION_ID, [])
    lose_faction_armies = {
        army_id
        for army_id in armies_at_lose_location
        if army_to_faction.get(army_id) == DEMO_LOSE_FACTION_ID
    }
    assert not lose_faction_armies, (
        f"{DEMO_LOSE_FACTION_ID!r} army at {DEMO_LOSE_LOCATION_ID!r} at tick 0: "
        f"{lose_faction_armies}"
    )


def test_no_opposing_armies_share_location_at_tick_zero() -> None:
    """No two armies from different factions may share a location at tick 0.

    military_battle_service.resolve_battles groups armies by location and fires whenever
    2+ factions meet. Co-located opposing armies at tick 0 guarantee a battle resolves
    on the very first tick before the player can act.
    """
    army_to_faction = _army_to_faction()
    occupancies = _tick_zero_occupancies()
    for loc_id, armies in occupancies.items():
        factions = {army_to_faction[a] for a in armies if a in army_to_faction}
        assert len(factions) <= 1, (
            f"Opposing armies share {loc_id!r} at tick 0: factions={factions}, armies={armies}"
        )
