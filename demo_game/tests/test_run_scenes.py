"""Tests for S10.4 rumor-arc scene classes: SpreadRumorScene, RumorTraceDisplay, CorrectRumorScene."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from demo_game.run_scenes import CorrectRumorScene, RumorTraceDisplay, SpreadRumorScene


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner(
    dry_run: bool = False,
    clock_tick: int = 5,
    spread_response: dict | None = None,
    trace_response: dict | None = None,
    correct_response: dict | None = None,
    planted_event_id: str = "",
) -> MagicMock:
    runner = MagicMock()
    runner.dry_run = dry_run

    # Always set planted_event_id as a real str so the falsy guard works correctly.
    # MagicMock auto-creates attributes as truthy Mocks, which defeats `if not event_id`.
    runner.planted_event_id = planted_event_id

    runner.client.get_clock_state.return_value = {"data": {"current_tick": clock_tick}}
    runner.client.spread_rumor.return_value = spread_response or {
        "data": {"event_id": "evt_rumor_lira_5", "npc_id": "lira_fence"}
    }
    runner.client.trace_rumor.return_value = trace_response or {
        "data": {
            "chain": [
                {"npc_id": "lira_fence", "learned_at_tick": 5, "knowledge_state": None},
                {"npc_id": "mira_innkeeper", "learned_at_tick": 6, "knowledge_state": None},
            ]
        }
    }
    runner.client.correct_rumor.return_value = correct_response or {
        "data": {"npc_id": "mira_innkeeper", "event_id": "evt_rumor_lira_5", "corrected": True}
    }
    return runner


# ---------------------------------------------------------------------------
# SpreadRumorScene
# ---------------------------------------------------------------------------

class TestSpreadRumorScene:
    def test_calls_spread_rumor_with_correct_args(self) -> None:
        runner = _make_runner(clock_tick=7)
        scene = SpreadRumorScene(
            name="plant",
            target_npc_id="lira_fence",
            rumor_text="The merchant is a spy.",
            severity=60,
        )
        scene.execute(runner)
        runner.client.spread_rumor.assert_called_once_with(
            target_npc_id="lira_fence",
            rumor_text="The merchant is a spy.",
            severity=60,
            tick_id=7,
        )

    def test_sets_planted_event_id_on_runner(self) -> None:
        runner = _make_runner()
        scene = SpreadRumorScene(name="plant", target_npc_id="lira_fence", rumor_text="lie", severity=50)
        scene.execute(runner)
        assert runner.planted_event_id == "evt_rumor_lira_5"

    def test_dry_run_skips_api_call(self) -> None:
        runner = _make_runner(dry_run=True)
        scene = SpreadRumorScene(name="plant", target_npc_id="lira_fence", rumor_text="lie", severity=50)
        scene.execute(runner)
        runner.client.spread_rumor.assert_not_called()

    def test_empty_event_id_still_sets_attr(self) -> None:
        runner = _make_runner(spread_response={"data": {}})
        scene = SpreadRumorScene(name="plant", target_npc_id="lira_fence", rumor_text="x", severity=10)
        scene.execute(runner)
        assert runner.planted_event_id == ""


# ---------------------------------------------------------------------------
# RumorTraceDisplay
# ---------------------------------------------------------------------------

class TestRumorTraceDisplay:
    def test_calls_trace_rumor_with_stored_event_id(self) -> None:
        runner = _make_runner(planted_event_id="evt_abc")
        scene = RumorTraceDisplay(name="trace")
        scene.execute(runner)
        runner.client.trace_rumor.assert_called_once_with("evt_abc")

    def test_dry_run_skips_api_call(self) -> None:
        runner = _make_runner(dry_run=True, planted_event_id="evt_abc")
        scene = RumorTraceDisplay(name="trace")
        scene.execute(runner)
        runner.client.trace_rumor.assert_not_called()

    def test_missing_event_id_prints_skip(self) -> None:
        runner = _make_runner()
        # no planted_event_id set
        scene = RumorTraceDisplay(name="trace")
        scene.execute(runner)
        runner.client.trace_rumor.assert_not_called()
        runner.print_ok.assert_called_once()
        assert "skip" in runner.print_ok.call_args[0][0].lower()

    def test_empty_chain_prints_not_propagated(self) -> None:
        runner = _make_runner(
            planted_event_id="evt_abc",
            trace_response={"data": {"chain": []}},
        )
        scene = RumorTraceDisplay(name="trace")
        scene.execute(runner)
        runner.print_ok.assert_called_once()
        assert "not propagated" in runner.print_ok.call_args[0][0].lower()

    def test_prints_one_line_per_hop(self) -> None:
        runner = _make_runner(planted_event_id="evt_abc")
        scene = RumorTraceDisplay(name="trace")
        scene.execute(runner)
        # 2 hops in default trace_response
        assert runner.print_ok.call_count == 2


# ---------------------------------------------------------------------------
# CorrectRumorScene
# ---------------------------------------------------------------------------

class TestCorrectRumorScene:
    def test_calls_correct_rumor_with_npc_and_event_id(self) -> None:
        runner = _make_runner(planted_event_id="evt_abc")
        scene = CorrectRumorScene(name="correct", npc_id="mira_innkeeper")
        scene.execute(runner)
        runner.client.correct_rumor.assert_called_once_with(
            npc_id="mira_innkeeper", event_id="evt_abc"
        )

    def test_dry_run_skips_api_call(self) -> None:
        runner = _make_runner(dry_run=True, planted_event_id="evt_abc")
        scene = CorrectRumorScene(name="correct", npc_id="mira_innkeeper")
        scene.execute(runner)
        runner.client.correct_rumor.assert_not_called()

    def test_missing_event_id_prints_skip(self) -> None:
        runner = _make_runner()
        scene = CorrectRumorScene(name="correct", npc_id="mira_innkeeper")
        scene.execute(runner)
        runner.client.correct_rumor.assert_not_called()
        runner.print_ok.assert_called_once()
        assert "skip" in runner.print_ok.call_args[0][0].lower()

    def test_prints_corrected_true(self) -> None:
        runner = _make_runner(planted_event_id="evt_abc")
        scene = CorrectRumorScene(name="correct", npc_id="mira_innkeeper")
        scene.execute(runner)
        msg: str = runner.print_ok.call_args[0][0]
        assert "corrected=True" in msg

    def test_prints_corrected_false_on_api_response(self) -> None:
        runner = _make_runner(
            planted_event_id="evt_abc",
            correct_response={"data": {"corrected": False}},
        )
        scene = CorrectRumorScene(name="correct", npc_id="mira_innkeeper")
        scene.execute(runner)
        msg: str = runner.print_ok.call_args[0][0]
        assert "corrected=False" in msg
