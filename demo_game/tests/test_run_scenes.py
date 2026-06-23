"""Tests for S10.4 rumor-arc scene classes: SpreadRumorScene, RumorTraceDisplay, CorrectRumorScene."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from demo_game.runners.run_scenes import CorrectRumorScene, RumorTraceDisplay, SpreadRumorScene


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


# ---------------------------------------------------------------------------
# Intrigue scenes (G3.1): DeceptionRevealScene + PlayerModelDisplay
# ---------------------------------------------------------------------------

from demo_game.runners.run_scenes import DeceptionRevealScene, PlayerModelDisplay  # noqa: E402


class TestDeceptionRevealScene:
    def test_dry_run_skips_api_call(self) -> None:
        runner = MagicMock()
        runner.dry_run = True
        DeceptionRevealScene(name="d", npc_id="lira_fence").execute(runner)
        runner.client.get_beliefs.assert_not_called()

    def test_surfaces_planted_deception(self) -> None:
        runner = MagicMock()
        runner.dry_run = False
        runner.client.get_beliefs.return_value = [
            {"content": "ordinary belief", "is_deception": False},
            {"content": "the mill is unguarded", "is_deception": True},
        ]
        DeceptionRevealScene(name="d", npc_id="lira_fence").execute(runner)
        printed = " ".join(str(c.args[0]) for c in runner.print_ok.call_args_list)
        assert "the mill is unguarded" in printed
        assert "deception" in printed.lower()

    def test_no_deception_prints_info(self) -> None:
        runner = MagicMock()
        runner.dry_run = False
        runner.client.get_beliefs.return_value = [{"content": "x", "is_deception": False}]
        DeceptionRevealScene(name="d", npc_id="lira_fence").execute(runner)
        printed = " ".join(str(c.args[0]) for c in runner.print_ok.call_args_list)
        assert "no flagged deception" in printed


class TestPlayerModelDisplay:
    def test_dry_run_skips_api_call(self) -> None:
        runner = MagicMock()
        runner.dry_run = True
        PlayerModelDisplay(name="pm", npc_id="mira_innkeeper").execute(runner)
        runner.client.get_player_model.assert_not_called()

    def test_prints_trust_and_intent(self) -> None:
        runner = MagicMock()
        runner.dry_run = False
        runner.client.get_player_model.return_value = {"perceived_trust": 72, "perceived_intent": "friendly"}
        PlayerModelDisplay(name="pm", npc_id="mira_innkeeper").execute(runner)
        printed = " ".join(str(c.args[0]) for c in runner.print_ok.call_args_list)
        assert "72" in printed and "friendly" in printed

    def test_none_model_prints_info(self) -> None:
        runner = MagicMock()
        runner.dry_run = False
        runner.client.get_player_model.return_value = None
        PlayerModelDisplay(name="pm", npc_id="mira_innkeeper").execute(runner)
        printed = " ".join(str(c.args[0]) for c in runner.print_ok.call_args_list)
        assert "no model" in printed


# ---------------------------------------------------------------------------
# BranchBeat (H2.8): scripted fork over the H2.1 branch primitive
# ---------------------------------------------------------------------------

from demo_game.runners.run_scenes import BranchBeat  # noqa: E402
import demo_game.runners.run_scenes as _rs  # noqa: E402
from demo_game.branches.branch_state import BranchState  # noqa: E402
from demo_game.branches.branch_node import BRANCH_ID_GARRICK  # noqa: E402


class TestBranchBeat:
    def _patch_state(self, monkeypatch):
        saved: dict = {}
        monkeypatch.setattr(_rs, "load_branch_state", lambda: BranchState())
        monkeypatch.setattr(_rs, "save_branch_state", lambda s: saved.update(state=s))
        return saved

    def test_dry_run_applies_no_effects(self, monkeypatch) -> None:
        self._patch_state(monkeypatch)
        runner = MagicMock()
        runner.dry_run = True
        BranchBeat(name="b", option_index=0).execute(runner)
        runner.client.adjust_npc_reputation.assert_not_called()

    def test_spare_option_applies_rep_effect_and_persists(self, monkeypatch) -> None:
        saved = self._patch_state(monkeypatch)
        runner = MagicMock()
        runner.dry_run = False
        BranchBeat(name="b", option_index=0).execute(runner)
        runner.client.adjust_npc_reputation.assert_called_once()
        assert saved["state"].has_chosen(BRANCH_ID_GARRICK)
        assert saved["state"].choice_for(BRANCH_ID_GARRICK).option_index == 0

    def test_turn_in_option_forks_to_other_outcome(self, monkeypatch) -> None:
        saved = self._patch_state(monkeypatch)
        runner = MagicMock()
        runner.dry_run = False
        BranchBeat(name="b", option_index=1).execute(runner)
        # option 1 = turn-in → city_guard faction in the rep call
        args = runner.client.adjust_npc_reputation.call_args.args
        assert "city_guard" in args
        assert saved["state"].choice_for(BRANCH_ID_GARRICK).option_index == 1

    def test_prior_choice_in_state_wins_for_replay(self, monkeypatch) -> None:
        # A prior turn-in choice in BranchState reproduces on replay regardless of option_index.
        monkeypatch.setattr(_rs, "load_branch_state",
                            lambda: BranchState().with_choice(BRANCH_ID_GARRICK, 1, "Turn him in"))
        monkeypatch.setattr(_rs, "save_branch_state", lambda s: None)
        runner = MagicMock()
        runner.dry_run = False
        BranchBeat(name="b", option_index=0).execute(runner)  # option_index ignored
        args = runner.client.adjust_npc_reputation.call_args.args
        assert "city_guard" in args
