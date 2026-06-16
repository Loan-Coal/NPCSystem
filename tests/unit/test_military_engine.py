"""Unit tests for MilitaryEngine — S6.5 (battle resolution + resource yield)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.military.military_engine import MilitaryEngine
from npc_engine.graph.military_writer import _validate_composition


@pytest.fixture
def military_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def engine(military_repo) -> MilitaryEngine:
    return MilitaryEngine(military_repo=military_repo)


# ---------------------------------------------------------------------------
# MilitaryEngine.run_tick — wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_returns_battles_and_yields(engine, military_repo) -> None:
    """run_tick returns battles_resolved and factions_yielded counts."""
    from npc_engine.engines.military.military_battle_service import BattleResult
    from npc_engine.engines.military.military_resource_service import ResourceYieldResult

    battle = BattleResult(
        location_id="loc-1",
        winner_faction_id="fa",
        loser_faction_id="fb",
        winner_strength_before=100,
        loser_strength_before=40,
        winner_damage=10,
        loser_damage=50,
        tick_id=5,
    )
    yield_res = ResourceYieldResult(
        faction_id="fa", total_yield=30, resources_depleted=0, tick_id=5
    )

    with (
        patch(
            "npc_engine.engines.military.military_engine.resolve_battles",
            new_callable=AsyncMock,
            return_value=[battle],
        ),
        patch(
            "npc_engine.engines.military.military_engine.process_resource_yield",
            new_callable=AsyncMock,
            return_value=[yield_res],
        ),
    ):
        result = await engine.run_tick(tick_id=5)

    assert result["battles_resolved"] == 1
    assert result["factions_yielded"] == 1


@pytest.mark.asyncio
async def test_run_tick_no_battles_no_yields(engine, military_repo) -> None:
    """With no conflicts and no resources, returns zeros."""
    with (
        patch(
            "npc_engine.engines.military.military_engine.resolve_battles",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.engines.military.military_engine.process_resource_yield",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await engine.run_tick(tick_id=0)

    assert result["battles_resolved"] == 0
    assert result["factions_yielded"] == 0


@pytest.mark.asyncio
async def test_run_tick_calls_both_services(engine, military_repo) -> None:
    """run_tick passes the injected port and tick to both services."""
    with (
        patch(
            "npc_engine.engines.military.military_engine.resolve_battles",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_battles,
        patch(
            "npc_engine.engines.military.military_engine.process_resource_yield",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_yield,
    ):
        await engine.run_tick(tick_id=42)

    mock_battles.assert_awaited_once_with(military_repo, tick_id=42)
    mock_yield.assert_awaited_once_with(military_repo, tick_id=42)


@pytest.mark.asyncio
async def test_run_tick_ignores_scheduler_session_kwarg(engine, military_repo) -> None:
    """run_tick accepts and ignores the scheduler's session= kwarg (SEV-24)."""
    with (
        patch(
            "npc_engine.engines.military.military_engine.resolve_battles",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.engines.military.military_engine.process_resource_yield",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await engine.run_tick(session=object(), tick_id=7)

    assert result == {"battles_resolved": 0, "factions_yielded": 0}


# ---------------------------------------------------------------------------
# Army composition validation (writer helper — unchanged from previous suite)
# ---------------------------------------------------------------------------


def test_valid_composition_serialises_to_json() -> None:
    """A well-formed composition dict is accepted and returns a JSON string."""
    import json

    result = _validate_composition({"infantry": 100, "cavalry": 50, "siege": 20})
    parsed = json.loads(result)

    assert parsed["infantry"] == 100
    assert parsed["cavalry"] == 50
    assert parsed["siege"] == 20


def test_missing_composition_key_raises_value_error() -> None:
    """A composition dict missing a required key raises ValueError."""
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_composition({"infantry": 100, "cavalry": 50})


def test_non_int_composition_value_raises_value_error() -> None:
    """A composition dict with a non-int value raises ValueError."""
    with pytest.raises(ValueError, match="must be int"):
        _validate_composition({"infantry": 100, "cavalry": 50, "siege": "twenty"})


def test_extra_keys_are_ignored() -> None:
    """Extra keys beyond the required three are silently dropped."""
    import json

    result = _validate_composition({"infantry": 10, "cavalry": 5, "siege": 2, "dragons": 1})
    parsed = json.loads(result)

    assert set(parsed.keys()) == {"infantry", "cavalry", "siege"}
