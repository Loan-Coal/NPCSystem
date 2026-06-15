"""Unit tests for NeedDecayEngine (Phase 7.3 Social Simulation).

The engine now depends on an injected NeedGraphPort (DEC-122 / SEV-24), so these
tests mock the port directly — no Neo4j session is involved.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.need.need_decay_engine import NeedDecayEngine


def _make_repo(rows: list[dict[str, Any]]) -> AsyncMock:
    """Build a mock NeedGraphPort returning ``rows`` and recording level writes."""
    repo = AsyncMock()
    repo.get_all_needs_with_location = AsyncMock(return_value=rows)
    repo.set_need_level = AsyncMock()
    return repo


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
async def test_level_decays_by_decay_rate():
    """Level drops by decay_rate each tick when no satisfier is present."""
    repo = _make_repo([_need(level=50, decay_rate=10, satisfaction_magnitude=0)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=1)

    assert result["needs_updated"] == 1
    repo.set_need_level.assert_called_once_with(need_id="n-1", level=40)


@pytest.mark.asyncio
async def test_level_does_not_go_below_zero():
    """Level is clamped to 0 even when decay would push it negative."""
    repo = _make_repo([_need(level=5, decay_rate=20, satisfaction_magnitude=0)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=2)

    assert result["needs_updated"] == 1
    assert result["needs_critical"] == 1
    repo.set_need_level.assert_called_once_with(need_id="n-1", level=0)


@pytest.mark.asyncio
async def test_satisfier_restores_magnitude():
    """When a satisfier is present, net change = -decay_rate + magnitude."""
    repo = _make_repo([_need(level=50, decay_rate=10, satisfaction_magnitude=15)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=3)

    assert result["needs_updated"] == 1
    repo.set_need_level.assert_called_once_with(need_id="n-1", level=55)


@pytest.mark.asyncio
async def test_level_capped_at_100():
    """Level cannot exceed 100 even with a large satisfier magnitude."""
    repo = _make_repo([_need(level=95, decay_rate=5, satisfaction_magnitude=30)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=4)

    assert result["needs_updated"] == 1
    repo.set_need_level.assert_called_once_with(need_id="n-1", level=100)


@pytest.mark.asyncio
async def test_no_write_when_level_unchanged():
    """When decay equals magnitude (net 0), no DB write is issued."""
    repo = _make_repo([_need(level=50, decay_rate=10, satisfaction_magnitude=10)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=5)

    assert result["needs_updated"] == 0
    repo.set_need_level.assert_not_called()


@pytest.mark.asyncio
async def test_empty_needs_returns_zero_counts():
    """When no needs exist, result has zeroes and no DB write occurs."""
    repo = _make_repo([])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=1)

    assert result == {"needs_updated": 0, "needs_critical": 0}
    repo.set_need_level.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    """The scheduler still passes session=...; the engine accepts and ignores it."""
    repo = _make_repo([_need(level=50, decay_rate=10, satisfaction_magnitude=0)])
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(session=object(), tick_id=7)

    assert result["needs_updated"] == 1
    repo.set_need_level.assert_called_once_with(need_id="n-1", level=40)


@pytest.mark.asyncio
async def test_multiple_needs_updated_independently():
    """Multiple needs each decay independently; critical count accumulates."""
    repo = _make_repo(
        [
            _need(need_id="n-1", level=30, decay_rate=10, satisfaction_magnitude=0),
            _need(need_id="n-2", level=5, decay_rate=10, satisfaction_magnitude=0),
            _need(need_id="n-3", level=50, decay_rate=5, satisfaction_magnitude=5),
        ]
    )
    engine = NeedDecayEngine(need_repo=repo)

    result = await engine.run_tick(tick_id=6)

    # n-1: 30-10=20, n-2: 5-10=0 (critical), n-3: net=0 (no write)
    assert result["needs_updated"] == 2
    assert result["needs_critical"] == 1
    assert repo.set_need_level.call_count == 2
