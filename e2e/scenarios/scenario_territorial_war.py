"""
E2E scenario: Territorial War (Phase 7.4).

Seeds two armies at the same location (different factions) and verifies
that get_armies_in_conflict detects them. Then runs a MilitaryEngine tick
and confirms the stub returns skipped=True.

Uses mock graph layer to avoid live DB dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.military.military_engine import MilitaryEngine
from npc_engine.graph.military_queries import get_armies_in_conflict


async def _aiter(*records):
    """Yield each record in turn, simulating a Neo4j async result stream."""
    for record in records:
        yield record


@pytest.mark.asyncio
async def test_armies_in_conflict_detected():
    """Two armies from different factions at the same location are flagged as a conflict."""
    session = AsyncMock()
    record = {
        "location_id": "loc-border-pass",
        "faction_ids": ["faction-north", "faction-south"],
        "army_count": 2,
    }
    # session.run is awaited; its return value is then iterated with `async for`
    session.run.return_value = _aiter(record)

    conflicts = await get_armies_in_conflict(session)

    assert len(conflicts) == 1
    assert set(conflicts[0]["faction_ids"]) == {"faction-north", "faction-south"}
    assert conflicts[0]["location_id"] == "loc-border-pass"


@pytest.mark.asyncio
async def test_military_engine_tick_resolves_battles_and_yields():
    """MilitaryEngine.run_tick returns battles_resolved and factions_yielded counts."""
    from unittest.mock import patch

    from npc_engine.engines.military.military_battle_service import BattleResult
    from npc_engine.engines.military.military_resource_service import ResourceYieldResult

    mock_repo = AsyncMock()
    engine = MilitaryEngine(military_repo=mock_repo)

    battle = BattleResult(
        location_id="loc-border-pass",
        winner_faction_id="faction-north",
        loser_faction_id="faction-south",
        winner_strength_before=100,
        loser_strength_before=60,
        winner_damage=15,
        loser_damage=50,
        tick_id=10,
    )
    yield_res = ResourceYieldResult(
        faction_id="faction-north", total_yield=20, resources_depleted=0, tick_id=10
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
        result = await engine.run_tick(tick_id=10)

    assert result["battles_resolved"] == 1
    assert result["factions_yielded"] == 1


@pytest.mark.asyncio
async def test_no_armies_means_no_conflict():
    """When no armies are present, get_armies_in_conflict returns an empty list."""
    session = AsyncMock()
    # Empty async generator — no records returned
    session.run.return_value = _aiter()

    conflicts = await get_armies_in_conflict(session)

    assert conflicts == []
