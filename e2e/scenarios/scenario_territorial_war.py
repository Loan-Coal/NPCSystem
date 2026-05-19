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
async def test_military_engine_tick_returns_skipped():
    """MilitaryEngine.run_tick is a no-op stub and must return skipped=True."""
    session = AsyncMock()
    engine = MilitaryEngine()

    result = await engine.run_tick(session, tick_id=10)

    assert result["skipped"] is True
    assert "reason" in result


@pytest.mark.asyncio
async def test_no_armies_means_no_conflict():
    """When no armies are present, get_armies_in_conflict returns an empty list."""
    session = AsyncMock()
    # Empty async generator — no records returned
    session.run.return_value = _aiter()

    conflicts = await get_armies_in_conflict(session)

    assert conflicts == []
