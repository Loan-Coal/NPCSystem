"""
Module: military_battle_service
Layer: engines
Purpose: Battle resolution — detect opposing armies at the same location, determine
         winner by strength, apply damage to both sides, update CONTROLS/OCCUPIES
         edges, and emit a battle Event.
Does NOT: call LLMs, manage resource yield, run tick scheduling, or hold a Neo4j session.
Dependencies injected: MilitaryGraphPort (via resolve_battles).
Used by: npc_engine.engines.military.military_engine
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from npc_engine.engines.ports.military_port import MilitaryGraphPort

_LOGGER = logging.getLogger(__name__)

FULL_CONTROL_STRENGTH = 100
BATTLE_EVENT_SEVERITY = 80
BATTLE_WINNER_DAMAGE_DIVISOR = 4  # winner loses loser_strength // divisor
BATTLE_LOSER_DAMAGE_DIVISOR = 2   # loser loses winner_strength // divisor


class BattleResult(BaseModel):
    """Outcome of a single battle at one location."""

    location_id: str
    winner_faction_id: str
    loser_faction_id: str
    winner_strength_before: int
    loser_strength_before: int
    winner_damage: int
    loser_damage: int
    tick_id: int


async def resolve_battles(
    military_repo: MilitaryGraphPort,
    *,
    tick_id: int,
) -> list[BattleResult]:
    """Detect all locations with opposing armies and resolve each battle.

    For each conflict location:
    - Groups armies by faction and sums strength.
    - The faction with higher total strength wins.
    - Winner loses loser_strength // BATTLE_WINNER_DAMAGE_DIVISOR.
    - Loser loses winner_strength // BATTLE_LOSER_DAMAGE_DIVISOR.
    - Winner gains/updates CONTROLS edge; loser's CONTROLS edge is removed.
    - A battle Event node is emitted.

    Fallback: Neo4j unavailable → raises GraphUnavailableError (propagated to engine).

    Args:
        military_repo: Military-domain graph port (owns its sessions).
        tick_id: Current game tick ID.

    Returns:
        List of BattleResult, one per resolved battle.
    """
    conflicts = await military_repo.get_armies_in_conflict()
    results: list[BattleResult] = []

    for conflict in conflicts:
        location_id: str = conflict["location_id"]
        battle = await _resolve_one_battle(military_repo, location_id=location_id, tick_id=tick_id)
        if battle is not None:
            results.append(battle)

    return results


async def _resolve_one_battle(
    military_repo: MilitaryGraphPort,
    *,
    location_id: str,
    tick_id: int,
) -> BattleResult | None:
    """Resolve a battle at a single location.

    Returns None if the location no longer has opposing armies (race condition guard).
    """
    armies = await military_repo.get_army_at_location(location_id=location_id)
    faction_strengths = _sum_strength_by_faction(armies)

    if len(faction_strengths) < 2:
        return None

    winner_id, loser_id = _pick_winner_loser(faction_strengths)
    winner_str = faction_strengths[winner_id]
    loser_str = faction_strengths[loser_id]

    winner_damage = loser_str // BATTLE_WINNER_DAMAGE_DIVISOR
    loser_damage = winner_str // BATTLE_LOSER_DAMAGE_DIVISOR

    await _apply_battle_damage(military_repo, armies=armies, faction_strengths=faction_strengths,
                               winner_id=winner_id, loser_id=loser_id,
                               winner_damage=winner_damage, loser_damage=loser_damage)

    await military_repo.set_controls_location(
        faction_id=winner_id,
        location_id=location_id,
        control_strength=FULL_CONTROL_STRENGTH,
        contested_by=None,
    )
    await military_repo.remove_controls_location(
        faction_id=loser_id,
        location_id=location_id,
    )

    await _emit_battle_event(
        military_repo,
        location_id=location_id,
        winner_faction_id=winner_id,
        loser_faction_id=loser_id,
        tick_id=tick_id,
    )

    _LOGGER.info(
        "battle_resolved",
        extra={
            "location_id": location_id,
            "winner": winner_id,
            "loser": loser_id,
            "tick": tick_id,
        },
    )

    return BattleResult(
        location_id=location_id,
        winner_faction_id=winner_id,
        loser_faction_id=loser_id,
        winner_strength_before=winner_str,
        loser_strength_before=loser_str,
        winner_damage=winner_damage,
        loser_damage=loser_damage,
        tick_id=tick_id,
    )


def _sum_strength_by_faction(armies: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate total strength per faction from army list."""
    totals: dict[str, int] = {}
    for army in armies:
        faction_id: str = army["faction_id"]
        totals[faction_id] = totals.get(faction_id, 0) + int(army["strength"])
    return totals


def _pick_winner_loser(faction_strengths: dict[str, int]) -> tuple[str, str]:
    """Return (winner_id, loser_id) sorted by descending strength."""
    sorted_factions = sorted(faction_strengths, key=faction_strengths.__getitem__, reverse=True)
    return sorted_factions[0], sorted_factions[1]


async def _apply_battle_damage(
    military_repo: MilitaryGraphPort,
    *,
    armies: list[dict[str, Any]],
    faction_strengths: dict[str, int],
    winner_id: str,
    loser_id: str,
    winner_damage: int,
    loser_damage: int,
) -> None:
    """Apply calculated damage to each army in the battle."""
    for army in armies:
        faction_id: str = army["faction_id"]
        old_strength = int(army["strength"])

        if faction_id == winner_id:
            new_strength = max(0, old_strength - winner_damage)
        elif faction_id == loser_id:
            new_strength = max(0, old_strength - loser_damage)
        else:
            continue

        await military_repo.set_army_strength(army_id=army["army_id"], strength=new_strength)


async def _emit_battle_event(
    military_repo: MilitaryGraphPort,
    *,
    location_id: str,
    winner_faction_id: str,
    loser_faction_id: str,
    tick_id: int,
) -> None:
    """Write a public battle Event node via the military graph port.

    Args:
        military_repo: Military-domain graph port.
        location_id: Location where the battle occurred.
        winner_faction_id: Faction that won.
        loser_faction_id: Faction that lost.
        tick_id: Current game tick.
    """
    event_id = f"battle_{location_id}_{tick_id}_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    summary = (
        f"Battle at {location_id}: {winner_faction_id} defeated {loser_faction_id} "
        f"at tick {tick_id}"
    )
    await military_repo.emit_battle_event(
        event_id=event_id,
        summary=summary,
        severity=BATTLE_EVENT_SEVERITY,
        location_id=location_id,
        occurred_at=now,
        tick_id=tick_id,
        winner_faction_id=winner_faction_id,
    )
