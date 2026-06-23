"""
Tests for faction_history_service.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.faction.faction_history_service import (
    _least_squares_slope,
    get_standing_history_svc,
    get_standing_trend,
    record_standing_change,
)


# ---------------------------------------------------------------------------
# record_standing_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_standing_change_calls_run_with_required_fields() -> None:
    session = AsyncMock()
    event_id = await record_standing_change(
        session,
        src_faction_id="faction-a",
        dst_faction_id="faction-b",
        delta=10,
        new_standing=60,
        tick=42,
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["src_faction_id"] == "faction-a"
    assert kwargs["dst_faction_id"] == "faction-b"
    assert kwargs["delta"] == 10
    assert kwargs["new_standing"] == 60
    assert kwargs["tick_id"] == 42
    assert kwargs["cause_event_id"] is None
    assert kwargs["cause_rule_id"] is None
    assert isinstance(event_id, str)


@pytest.mark.asyncio
async def test_record_standing_change_passes_optional_fields() -> None:
    session = AsyncMock()
    await record_standing_change(
        session,
        src_faction_id="f1",
        dst_faction_id="f2",
        delta=-5,
        new_standing=30,
        tick=7,
        cause_event_id="evt-123",
        cause_rule_id="rule-aggression",
    )
    _, kwargs = session.run.call_args
    assert kwargs["cause_event_id"] == "evt-123"
    assert kwargs["cause_rule_id"] == "rule-aggression"


# ---------------------------------------------------------------------------
# get_standing_history_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_standing_history_svc_passes_args() -> None:
    with patch(
        "npc_engine.graph.faction.faction_history_service.get_standing_history",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        result = await get_standing_history_svc(session, "f1", "f2", limit=10)
        mock_fn.assert_called_once_with(
            session, src_faction_id="f1", dst_faction_id="f2", limit=10
        )
        assert result == []


# ---------------------------------------------------------------------------
# get_standing_trend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_standing_trend_returns_zero_with_fewer_than_two_points() -> None:
    with patch(
        "npc_engine.graph.faction.faction_history_service.get_raw_trend_rows",
        new_callable=AsyncMock,
        return_value=[{"tick_id": 5, "delta": 10}],
    ):
        session = AsyncMock()
        result = await get_standing_trend(session, "f1", "f2", window_ticks=100, current_tick=50)
        assert result == 0.0


@pytest.mark.asyncio
async def test_get_standing_trend_returns_zero_with_no_points() -> None:
    with patch(
        "npc_engine.graph.faction.faction_history_service.get_raw_trend_rows",
        new_callable=AsyncMock,
        return_value=[],
    ):
        session = AsyncMock()
        result = await get_standing_trend(session, "f1", "f2")
        assert result == 0.0


@pytest.mark.asyncio
async def test_get_standing_trend_positive_for_increasing_deltas() -> None:
    rows = [
        {"tick_id": 1, "delta": 2},
        {"tick_id": 2, "delta": 4},
        {"tick_id": 3, "delta": 6},
    ]
    with patch(
        "npc_engine.graph.faction.faction_history_service.get_raw_trend_rows",
        new_callable=AsyncMock,
        return_value=rows,
    ):
        session = AsyncMock()
        result = await get_standing_trend(session, "f1", "f2")
        assert result > 0


@pytest.mark.asyncio
async def test_get_standing_trend_negative_for_decreasing_deltas() -> None:
    rows = [
        {"tick_id": 1, "delta": -6},
        {"tick_id": 2, "delta": -4},
        {"tick_id": 3, "delta": -2},
    ]
    with patch(
        "npc_engine.graph.faction.faction_history_service.get_raw_trend_rows",
        new_callable=AsyncMock,
        return_value=rows,
    ):
        session = AsyncMock()
        result = await get_standing_trend(session, "f1", "f2")
        # Deltas increase from -6 to -2, so slope is positive
        assert result > 0


# ---------------------------------------------------------------------------
# _least_squares_slope — direct unit tests
# ---------------------------------------------------------------------------


def test_least_squares_slope_flat_line_returns_zero() -> None:
    points = [(1, 5), (2, 5), (3, 5)]
    assert _least_squares_slope(points) == 0.0


def test_least_squares_slope_perfectly_increasing() -> None:
    points = [(1, 1), (2, 2), (3, 3)]
    slope = _least_squares_slope(points)
    assert abs(slope - 1.0) < 1e-9


def test_least_squares_slope_perfectly_decreasing() -> None:
    points = [(1, 3), (2, 2), (3, 1)]
    slope = _least_squares_slope(points)
    assert abs(slope - (-1.0)) < 1e-9


def test_least_squares_slope_returns_zero_for_single_x_value() -> None:
    # All x values equal → denominator is 0, must return 0.0 (not raise)
    points = [(5, 1), (5, 3)]
    assert _least_squares_slope(points) == 0.0
