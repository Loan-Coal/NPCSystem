"""Unit tests for NeedDecayEngine (Phase 7.3 Social Simulation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.need.need_decay_engine import NeedDecayEngine


@pytest.fixture
def engine() -> NeedDecayEngine:
    return NeedDecayEngine()


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


def _need(
    need_id: str = "n-1",
    kind: str = "hunger",
    level: int = 50,
    decay_rate: int = 10,
    character_id: str = "char-1",
    location_id: str | None = None,
    satisfaction_magnitude: int = 0,
) -> dict:
    return {
        "need_id": need_id,
        "kind": kind,
        "level": level,
        "decay_rate": decay_rate,
        "character_id": character_id,
        "location_id": location_id,
        "satisfaction_magnitude": satisfaction_magnitude,
    }


# ---------------------------------------------------------------------------
# Core decay logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_level_decays_by_decay_rate(engine, session):
    """Level drops by decay_rate each tick when no satisfier is present."""
    need = _need(level=50, decay_rate=10, satisfaction_magnitude=0)

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[need]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=1)

    assert result["needs_updated"] == 1
    mock_set.assert_called_once_with(session, need_id="n-1", level=40)


@pytest.mark.asyncio
async def test_level_does_not_go_below_zero(engine, session):
    """Level is clamped to 0 even when decay would push it negative."""
    need = _need(level=5, decay_rate=20, satisfaction_magnitude=0)

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[need]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=2)

    assert result["needs_updated"] == 1
    assert result["needs_critical"] == 1
    mock_set.assert_called_once_with(session, need_id="n-1", level=0)


@pytest.mark.asyncio
async def test_satisfier_restores_magnitude(engine, session):
    """When a satisfier is present, net change = -decay_rate + magnitude."""
    need = _need(level=50, decay_rate=10, satisfaction_magnitude=15)

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[need]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=3)

    assert result["needs_updated"] == 1
    mock_set.assert_called_once_with(session, need_id="n-1", level=55)


@pytest.mark.asyncio
async def test_level_capped_at_100(engine, session):
    """Level cannot exceed 100 even with a large satisfier magnitude."""
    need = _need(level=95, decay_rate=5, satisfaction_magnitude=30)

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[need]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=4)

    assert result["needs_updated"] == 1
    mock_set.assert_called_once_with(session, need_id="n-1", level=100)


@pytest.mark.asyncio
async def test_no_write_when_level_unchanged(engine, session):
    """When decay equals magnitude (net 0), no DB write is issued."""
    need = _need(level=50, decay_rate=10, satisfaction_magnitude=10)

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[need]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=5)

    assert result["needs_updated"] == 0
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_empty_needs_returns_zero_counts(engine, session):
    """When no needs exist, result has zeroes and no DB write occurs."""
    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=1)

    assert result == {"needs_updated": 0, "needs_critical": 0}
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_needs_updated_independently(engine, session):
    """Multiple needs each decay independently; critical count accumulates."""
    needs = [
        _need(need_id="n-1", level=30, decay_rate=10, satisfaction_magnitude=0),
        _need(need_id="n-2", level=5, decay_rate=10, satisfaction_magnitude=0),
        _need(need_id="n-3", level=50, decay_rate=5, satisfaction_magnitude=5),
    ]

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=needs),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=6)

    # n-1: 30-10=20, n-2: 5-10=0 (critical), n-3: net=0 (no write)
    assert result["needs_updated"] == 2
    assert result["needs_critical"] == 1
    assert mock_set.call_count == 2
