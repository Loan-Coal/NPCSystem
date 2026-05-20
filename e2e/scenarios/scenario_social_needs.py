"""
E2E scenario: Social Needs Decay (Phase 7.3).

Verifies that:
1. A character's hunger need decays by decay_rate each tick with no satisfier.
2. After 5 ticks, a level-50 / decay_rate-10 need hits 0 (critical).
3. Placing the character at a location with SATISFIES_NEED restores magnitude
   points per tick, preventing critical level.

Uses mock graph layer to avoid live DB dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

import pytest

from npc_engine.engines.need.need_decay_engine import NeedDecayEngine


def _row(
    need_id: str = "need-hunger-01",
    level: int = 50,
    decay_rate: int = 10,
    satisfaction_magnitude: int = 0,
) -> dict:
    return {
        "need_id": need_id,
        "kind": "hunger",
        "level": level,
        "decay_rate": decay_rate,
        "character_id": "char-hermit",
        "location_id": None,
        "satisfaction_magnitude": satisfaction_magnitude,
    }


@pytest.mark.asyncio
async def test_hunger_decays_to_critical_after_five_ticks():
    """
    Simulate 5 ticks of decay (decay_rate=10, level starts at 50).
    After 5 ticks with no satisfier the level should reach 0.
    """
    session = AsyncMock()
    engine = NeedDecayEngine()

    written_levels: list[int] = []

    async def _fake_set(sess, *, need_id, level):
        written_levels.append(level)

    current_level = 50

    def _make_query_mock():
        async def _query(sess):
            return [_row(level=current_level)]
        return _query

    # Simulate 5 ticks manually, each time advancing the mock's returned level.
    levels_over_time: list[int] = [50]
    for tick in range(1, 6):
        tick_level = max(0, 50 - tick * 10)
        levels_over_time.append(tick_level)

    all_written: list[int] = []

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(side_effect=lambda sess, *, need_id, level: all_written.append(level)),
        ),
    ):
        tick_level = 50
        for tick in range(1, 6):
            expected_level = max(0, tick_level - 10)
            with patch(
                "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
                new=AsyncMock(return_value=[_row(level=tick_level)]),
            ):
                result = await engine.run_tick(session, tick_id=tick)
            tick_level = expected_level

    # All 5 ticks should have written declining levels
    assert all_written == [40, 30, 20, 10, 0]
    # The last tick should have been marked critical
    assert result["needs_critical"] == 1


@pytest.mark.asyncio
async def test_satisfier_prevents_critical():
    """
    With decay_rate=10 and satisfaction_magnitude=10, net change is 0.
    Level should never drop and set_need_level should never be called.
    """
    session = AsyncMock()
    engine = NeedDecayEngine()

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[_row(level=50, decay_rate=10, satisfaction_magnitude=10)]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=1)

    assert result["needs_updated"] == 0
    assert result["needs_critical"] == 0
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_partial_restoration_slows_decay():
    """
    With decay_rate=10 and satisfaction_magnitude=6, net decay = 4 per tick.
    After 1 tick level should go from 50 → 46.
    """
    session = AsyncMock()
    engine = NeedDecayEngine()

    with (
        patch(
            "npc_engine.engines.need.need_decay_engine.get_all_needs_with_location",
            new=AsyncMock(return_value=[_row(level=50, decay_rate=10, satisfaction_magnitude=6)]),
        ),
        patch(
            "npc_engine.engines.need.need_decay_engine.set_need_level",
            new=AsyncMock(),
        ) as mock_set,
    ):
        await engine.run_tick(session, tick_id=1)

    mock_set.assert_called_once_with(session, need_id="need-hunger-01", level=46)
