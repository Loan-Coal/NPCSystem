"""Tests for military_battle_service — S6.5 battle resolution (port-injected)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.military.military_battle_service import (
    BattleResult,
    resolve_battles,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def military_repo() -> AsyncMock:
    """A mock MilitaryGraphPort with no conflicts by default."""
    repo = AsyncMock()
    repo.get_armies_in_conflict.return_value = []
    return repo


# ---------------------------------------------------------------------------
# resolve_battles — no conflicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_battles_no_conflicts_returns_empty(military_repo) -> None:
    """When no location has multiple factions, no battles occur."""
    result = await resolve_battles(military_repo, tick_id=1)

    assert result == []


# ---------------------------------------------------------------------------
# resolve_battles — single conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_battles_winner_determined_by_strength(military_repo) -> None:
    """Faction with higher total strength wins the battle."""
    conflict = {"location_id": "loc-1", "faction_ids": ["faction-a", "faction-b"], "army_count": 2}
    armies = [
        {"army_id": "army-1", "faction_id": "faction-a", "strength": 100, "since_tick": 0},
        {"army_id": "army-2", "faction_id": "faction-b", "strength": 40, "since_tick": 0},
    ]
    military_repo.get_armies_in_conflict.return_value = [conflict]
    military_repo.get_army_at_location.return_value = armies

    result = await resolve_battles(military_repo, tick_id=5)

    assert len(result) == 1
    battle: BattleResult = result[0]
    assert battle.winner_faction_id == "faction-a"
    assert battle.loser_faction_id == "faction-b"
    assert battle.location_id == "loc-1"
    assert battle.tick_id == 5


@pytest.mark.asyncio
async def test_resolve_battles_winner_takes_control(military_repo) -> None:
    """Winner faction gets CONTROLS edge set; loser CONTROLS edge removed."""
    conflict = {"location_id": "loc-1", "faction_ids": ["faction-a", "faction-b"], "army_count": 2}
    armies = [
        {"army_id": "army-1", "faction_id": "faction-a", "strength": 100, "since_tick": 0},
        {"army_id": "army-2", "faction_id": "faction-b", "strength": 40, "since_tick": 0},
    ]
    military_repo.get_armies_in_conflict.return_value = [conflict]
    military_repo.get_army_at_location.return_value = armies

    await resolve_battles(military_repo, tick_id=5)

    military_repo.set_controls_location.assert_awaited_once()
    call_kwargs = military_repo.set_controls_location.await_args.kwargs
    assert call_kwargs["faction_id"] == "faction-a"
    assert call_kwargs["location_id"] == "loc-1"

    military_repo.remove_controls_location.assert_awaited_once()
    rm_kwargs = military_repo.remove_controls_location.await_args.kwargs
    assert rm_kwargs["faction_id"] == "faction-b"


@pytest.mark.asyncio
async def test_resolve_battles_army_strengths_updated(military_repo) -> None:
    """Both winner and loser army strengths are updated after battle."""
    conflict = {"location_id": "loc-1", "faction_ids": ["faction-a", "faction-b"], "army_count": 2}
    armies = [
        {"army_id": "army-1", "faction_id": "faction-a", "strength": 100, "since_tick": 0},
        {"army_id": "army-2", "faction_id": "faction-b", "strength": 40, "since_tick": 0},
    ]
    military_repo.get_armies_in_conflict.return_value = [conflict]
    military_repo.get_army_at_location.return_value = armies

    result = await resolve_battles(military_repo, tick_id=5)

    # set_army_strength called for both armies
    assert military_repo.set_army_strength.await_count == 2
    battle = result[0]
    # winner damage = loser_strength // 4 = 10
    assert battle.winner_damage == 40 // 4
    # loser damage = winner_strength // 2 = 50
    assert battle.loser_damage == 100 // 2


@pytest.mark.asyncio
async def test_resolve_battles_event_emitted(military_repo) -> None:
    """A battle event is emitted for each resolved battle."""
    conflict = {"location_id": "loc-1", "faction_ids": ["faction-a", "faction-b"], "army_count": 2}
    armies = [
        {"army_id": "army-1", "faction_id": "faction-a", "strength": 80, "since_tick": 0},
        {"army_id": "army-2", "faction_id": "faction-b", "strength": 30, "since_tick": 0},
    ]
    military_repo.get_armies_in_conflict.return_value = [conflict]
    military_repo.get_army_at_location.return_value = armies

    await resolve_battles(military_repo, tick_id=5)

    military_repo.emit_battle_event.assert_awaited_once()
    emit_kwargs = military_repo.emit_battle_event.await_args.kwargs
    assert emit_kwargs["location_id"] == "loc-1"
    assert emit_kwargs["tick_id"] == 5
    assert emit_kwargs["winner_faction_id"] == "faction-a"


@pytest.mark.asyncio
async def test_resolve_battles_multiple_conflicts(military_repo) -> None:
    """Multiple conflict locations each produce a BattleResult."""
    conflicts = [
        {"location_id": "loc-1", "faction_ids": ["fa", "fb"], "army_count": 2},
        {"location_id": "loc-2", "faction_ids": ["fa", "fc"], "army_count": 2},
    ]

    def armies_for_location(*, location_id):
        if location_id == "loc-1":
            return [
                {"army_id": "a1", "faction_id": "fa", "strength": 60, "since_tick": 0},
                {"army_id": "a2", "faction_id": "fb", "strength": 20, "since_tick": 0},
            ]
        return [
            {"army_id": "a3", "faction_id": "fa", "strength": 50, "since_tick": 0},
            {"army_id": "a4", "faction_id": "fc", "strength": 10, "since_tick": 0},
        ]

    military_repo.get_armies_in_conflict.return_value = conflicts
    military_repo.get_army_at_location.side_effect = armies_for_location

    result = await resolve_battles(military_repo, tick_id=10)

    assert len(result) == 2
    location_ids = {r.location_id for r in result}
    assert location_ids == {"loc-1", "loc-2"}


# ---------------------------------------------------------------------------
# BattleResult model
# ---------------------------------------------------------------------------


def test_battle_result_model() -> None:
    """BattleResult is a valid Pydantic model with expected fields."""
    br = BattleResult(
        location_id="loc-1",
        winner_faction_id="fa",
        loser_faction_id="fb",
        winner_strength_before=100,
        loser_strength_before=40,
        winner_damage=10,
        loser_damage=50,
        tick_id=5,
    )
    assert br.winner_faction_id == "fa"
    assert br.loser_damage == 50
