"""
Unit tests for ISSUE-165: ClockPort is the single read-only tick abstraction.

Verifies that GameClock structurally satisfies ClockPort, and that the port
stays read-only so engines cannot advance the authoritative clock.
"""

from __future__ import annotations

import asyncio

from npc_engine.engines.ports.clock_port import ClockPort
from npc_engine.scheduler.game_clock import GameClock


# ---------------------------------------------------------------------------
# Structural conformance
# ---------------------------------------------------------------------------


def test_game_clock_satisfies_clock_port():
    """GameClock must be assignable to ClockPort and expose current_tick."""
    clock: ClockPort = GameClock(mode="game_driven")
    assert clock.current_tick == 0


def test_current_tick_tracks_advance():
    """current_tick must reflect the tick_id mutated by advance()."""
    clock = GameClock(mode="game_driven")
    asyncio.run(clock.advance(tick_delta=3, time_delta_seconds=0))
    assert clock.current_tick == 3
    assert clock.current_tick == clock.state.tick_id


# ---------------------------------------------------------------------------
# Read-only contract
# ---------------------------------------------------------------------------


def test_clock_port_does_not_expose_advance():
    """The port must stay read-only: only the scheduler/lifespan may mutate the clock."""
    assert not hasattr(ClockPort, "advance")


def test_clock_port_does_not_expose_restore():
    """restore() is a startup-only hydration hook and must not leak into the port."""
    assert not hasattr(ClockPort, "restore")
