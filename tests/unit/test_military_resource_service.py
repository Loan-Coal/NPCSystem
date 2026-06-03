"""Tests for military_resource_service — S6.5 resource yield and depletion."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.military.military_resource_service import (
    ResourceYieldResult,
    process_resource_yield,
)


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# process_resource_yield — no resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_resource_yield_no_resources_returns_empty(session) -> None:
    """When no faction controls resource-producing locations, returns empty list."""
    with patch(
        "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await process_resource_yield(session, tick_id=1)

    assert result == []


# ---------------------------------------------------------------------------
# process_resource_yield — single faction, single resource
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_resource_yield_adds_to_treasury(session) -> None:
    """Faction treasury is credited with resource yield."""
    rows = [
        {
            "faction_id": "faction-a",
            "resource_node_id": "res-1",
            "yield_per_tick": 50,
            "depletion": 80,
        }
    ]

    with (
        patch(
            "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.add_faction_treasury",
            new_callable=AsyncMock,
        ) as mock_treasury,
        patch(
            "npc_engine.engines.military.military_resource_service.set_resource_depletion",
            new_callable=AsyncMock,
        ),
    ):
        result = await process_resource_yield(session, tick_id=3)

    assert len(result) == 1
    assert result[0].faction_id == "faction-a"
    assert result[0].total_yield == 50
    mock_treasury.assert_awaited_once_with(session, faction_id="faction-a", amount=50)


@pytest.mark.asyncio
async def test_process_resource_yield_decrements_depletion(session) -> None:
    """ResourceNode depletion is decremented by DEPLETION_PER_TICK."""
    from npc_engine.engines.military.military_resource_service import DEPLETION_PER_TICK

    rows = [
        {
            "faction_id": "faction-a",
            "resource_node_id": "res-1",
            "yield_per_tick": 30,
            "depletion": 10,
        }
    ]

    with (
        patch(
            "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.add_faction_treasury",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.set_resource_depletion",
            new_callable=AsyncMock,
        ) as mock_deplete,
    ):
        await process_resource_yield(session, tick_id=3)

    mock_deplete.assert_awaited_once_with(
        session,
        resource_node_id="res-1",
        depletion=10 - DEPLETION_PER_TICK,
    )


@pytest.mark.asyncio
async def test_process_resource_yield_zero_depletion_skipped(session) -> None:
    """Resource nodes with depletion=0 are not yielded (fully depleted)."""
    rows = [
        {
            "faction_id": "faction-a",
            "resource_node_id": "res-1",
            "yield_per_tick": 50,
            "depletion": 0,
        }
    ]

    with (
        patch(
            "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.add_faction_treasury",
            new_callable=AsyncMock,
        ) as mock_treasury,
        patch(
            "npc_engine.engines.military.military_resource_service.set_resource_depletion",
            new_callable=AsyncMock,
        ) as mock_deplete,
    ):
        result = await process_resource_yield(session, tick_id=3)

    assert result == []
    mock_treasury.assert_not_awaited()
    mock_deplete.assert_not_awaited()


# ---------------------------------------------------------------------------
# process_resource_yield — multiple factions, multiple resources
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_resource_yield_aggregates_per_faction(session) -> None:
    """Multiple resources for the same faction are summed into one treasury call."""
    rows = [
        {"faction_id": "faction-a", "resource_node_id": "res-1", "yield_per_tick": 30, "depletion": 50},
        {"faction_id": "faction-a", "resource_node_id": "res-2", "yield_per_tick": 20, "depletion": 40},
    ]

    with (
        patch(
            "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.add_faction_treasury",
            new_callable=AsyncMock,
        ) as mock_treasury,
        patch(
            "npc_engine.engines.military.military_resource_service.set_resource_depletion",
            new_callable=AsyncMock,
        ),
    ):
        result = await process_resource_yield(session, tick_id=5)

    assert len(result) == 1
    assert result[0].total_yield == 50
    mock_treasury.assert_awaited_once_with(session, faction_id="faction-a", amount=50)


@pytest.mark.asyncio
async def test_process_resource_yield_separate_factions(session) -> None:
    """Different factions each get separate treasury credits."""
    rows = [
        {"faction_id": "faction-a", "resource_node_id": "res-1", "yield_per_tick": 40, "depletion": 60},
        {"faction_id": "faction-b", "resource_node_id": "res-2", "yield_per_tick": 25, "depletion": 30},
    ]

    with (
        patch(
            "npc_engine.engines.military.military_resource_service.get_faction_resource_nodes",
            new_callable=AsyncMock,
            return_value=rows,
        ),
        patch(
            "npc_engine.engines.military.military_resource_service.add_faction_treasury",
            new_callable=AsyncMock,
        ) as mock_treasury,
        patch(
            "npc_engine.engines.military.military_resource_service.set_resource_depletion",
            new_callable=AsyncMock,
        ),
    ):
        result = await process_resource_yield(session, tick_id=5)

    assert len(result) == 2
    faction_yields = {r.faction_id: r.total_yield for r in result}
    assert faction_yields == {"faction-a": 40, "faction-b": 25}
    assert mock_treasury.await_count == 2


# ---------------------------------------------------------------------------
# ResourceYieldResult model
# ---------------------------------------------------------------------------


def test_resource_yield_result_model() -> None:
    """ResourceYieldResult is a valid Pydantic model."""
    ryr = ResourceYieldResult(
        faction_id="faction-a",
        total_yield=75,
        resources_depleted=1,
        tick_id=3,
    )
    assert ryr.total_yield == 75
    assert ryr.resources_depleted == 1
