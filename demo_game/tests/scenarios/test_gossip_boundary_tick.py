"""
Tests for GossipBoundaryTick and ACT 7's use of it (T2.4 live run).

Gossip runs every GOSSIP_TICK_INTERVAL (10) ticks. ACT 7 advanced the clock +2 blind, from
tick 6 to 8, so the gossip engine never ran, the planted lie never reached Mira, and
`correct_at_mira` died with HTTP 404 — visible only in a live run. GossipBoundaryTick reads
`next_gossip_tick` from GET /v1/clock/state and advances exactly to it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.runners.run import SCENES
from demo_game.runners.run_scenes import ClockTick, GossipBoundaryTick, RumorTraceDisplay, SpreadRumorScene


def _runner(state: dict, dry_run: bool = False) -> MagicMock:
    runner = MagicMock()
    runner.dry_run = dry_run
    runner.client.get_clock_state.return_value = {"success": True, "data": state}
    return runner


def test_advances_exactly_to_the_next_gossip_tick() -> None:
    runner = _runner({"tick_id": 6, "next_gossip_tick": 10})
    GossipBoundaryTick(name="g").execute(runner)
    runner.client.advance_clock.assert_called_once_with(delta_ticks=4)


def test_advances_one_tick_when_the_boundary_is_next() -> None:
    runner = _runner({"tick_id": 9, "next_gossip_tick": 10})
    GossipBoundaryTick(name="g").execute(runner)
    runner.client.advance_clock.assert_called_once_with(delta_ticks=1)


def test_missing_next_gossip_tick_fails_loudly() -> None:
    runner = _runner({"tick_id": 6})
    with pytest.raises(RuntimeError, match="next_gossip_tick"):
        GossipBoundaryTick(name="g").execute(runner)
    runner.client.advance_clock.assert_not_called()


def test_non_advancing_boundary_fails_loudly() -> None:
    runner = _runner({"tick_id": 10, "next_gossip_tick": 10})
    with pytest.raises(RuntimeError, match="next_gossip_tick"):
        GossipBoundaryTick(name="g").execute(runner)


def test_dry_run_makes_no_api_call() -> None:
    runner = _runner({}, dry_run=True)
    GossipBoundaryTick(name="g").execute(runner)
    runner.client.get_clock_state.assert_not_called()
    runner.client.advance_clock.assert_not_called()


def test_act7_reaches_a_gossip_tick_between_planting_and_tracing() -> None:
    names = [s.name for s in SCENES]
    plant = names.index("plant_rumor")
    trace = names.index("trace_after_propagate")
    between = SCENES[plant + 1:trace]
    assert isinstance(SCENES[plant], SpreadRumorScene)
    assert isinstance(SCENES[trace], RumorTraceDisplay)
    assert any(isinstance(s, GossipBoundaryTick) for s in between)
    assert not any(isinstance(s, ClockTick) for s in between)
