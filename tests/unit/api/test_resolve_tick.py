"""
Unit tests for ISSUE-165 / D5: request-tick resolution semantics.

An absent tick means "now" (the authoritative clock). An explicit tick is an
intentional backdate, so callers can backlog events at a past tick. Before this,
the affected request fields defaulted to 0 and silently stamped writes with tick 0.
"""

from __future__ import annotations

import asyncio

from npc_engine.api.helpers import resolve_tick
from npc_engine.scheduler.game_clock import GameClock


def _clock_at(tick: int) -> GameClock:
    clock = GameClock(mode="game_driven")
    asyncio.run(clock.advance(tick_delta=tick, time_delta_seconds=0))
    return clock


def test_absent_tick_resolves_to_the_current_clock_tick():
    """None means "now" — not 0."""
    assert resolve_tick(None, _clock_at(12)) == 12


def test_explicit_tick_is_honoured_as_a_backdate():
    """An explicit past tick must survive, so events can be backlogged."""
    assert resolve_tick(3, _clock_at(12)) == 3


def test_explicit_zero_is_not_treated_as_absent():
    """Tick 0 is a legitimate value and must not fall back to the clock."""
    assert resolve_tick(0, _clock_at(12)) == 0


def test_future_tick_is_honoured():
    """resolve_tick does not clamp; scheduling ahead is the caller's business."""
    assert resolve_tick(99, _clock_at(12)) == 99
