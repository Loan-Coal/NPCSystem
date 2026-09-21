"""
Module: tests.unit.evals.test_arm_probe_run
Layer: test (unit)
Purpose: Unit tests for evals/arm_probe.py — _finish, _live_gates, and _run
         orchestration, with emphasis that a failing gate is *reported* as failing
         (exit code 1, FAILED line printed). All infrastructure mocked; no live services.
Dependencies: pytest, unittest.mock; evals.arm_probe, evals.arm_probe_models
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from arm_probe import _declared_arms, _finish, _live_gates, _observe_all, _run, main  # noqa: E402
from arm_probe_models import ArmObservation, GateResult  # noqa: E402

_PASS = GateResult(number=1, name="config", passed=True, detail=("ok",))
_FAIL = GateResult(number=1, name="config", passed=False, detail=("arms identical",))
_PASS2 = GateResult(number=2, name="corpus", passed=True, detail=("sha ok",))
_FAIL2 = GateResult(number=2, name="corpus", passed=False, detail=("item_count is 0",))


# ---------------------------------------------------------------------------
# _finish — the exit-code contract
# ---------------------------------------------------------------------------


def test_finish_returns_1_when_first_gate_failed(capsys: pytest.CaptureFixture[str]) -> None:
    """THE core contract: a failing gate must produce exit code 1 and a FAILED line."""
    code = _finish([_FAIL], arms={}, started=0.0)
    out = capsys.readouterr().out
    assert code == 1
    assert "RESULT: FAILED" in out
    assert "gate 1" in out


def test_finish_returns_0_when_all_pass(capsys: pytest.CaptureFixture[str]) -> None:
    """All gates passed → exit code 0 and 'passed' line."""
    code = _finish([_PASS, _PASS2], arms={"wide_rag": {}}, started=0.0)
    out = capsys.readouterr().out
    assert code == 0
    assert "all 2 gate(s) passed" in out


def test_finish_prints_each_gate_verdict(capsys: pytest.CaptureFixture[str]) -> None:
    """Every gate result is printed whether it passed or failed — evidence is always visible."""
    code = _finish([_PASS, _FAIL2], arms={}, started=0.0)
    out = capsys.readouterr().out
    assert "[GATE 1] PASS" in out
    assert "[GATE 2] FAIL" in out
    assert code == 1


def test_finish_names_the_first_failing_gate(capsys: pytest.CaptureFixture[str]) -> None:
    """_finish identifies which gate halted the run by number and name."""
    fail_gate = GateResult(number=3, name="isolation", passed=False, detail=("collision",))
    _finish([_PASS, _PASS2, fail_gate], arms={}, started=0.0)
    out = capsys.readouterr().out
    assert "gate 3 (isolation)" in out


def test_finish_with_empty_results_returns_0(capsys: pytest.CaptureFixture[str]) -> None:
    """No results is a degenerate but valid input; the probe ran nothing and passed."""
    code = _finish([], arms={}, started=0.0)
    assert code == 0


# ---------------------------------------------------------------------------
# _live_gates — early-exit and gate-4 path
# ---------------------------------------------------------------------------


def test_live_gates_gate2_failure_stops_before_gate4() -> None:
    """A failing gate 2 must not proceed to gate 4 — only one result is in the list."""
    with (
        patch("arm_probe.gate_2_corpus") as mock_g2,
        patch("arm_probe.gate_4_effect"),
        patch("arm_probe.corpus_fields", new=MagicMock()),
    ):
        mock_g2.return_value = _FAIL2
        results = _live_gates(MagicMock(), arms={"wide_rag": MagicMock()}, player_id="p1", selected="all")

    assert len(results) == 1
    assert results[0].passed is False


def test_live_gates_gate4_runs_when_gate2_passes() -> None:
    """After a passing gate 2 the probe proceeds to gate 4."""
    obs_stub = MagicMock()
    obs_stub.item_keys = ()
    obs_stub.tier_spend = ()
    obs_stub.total_tokens = 0
    obs_stub.npc_id = "captain_sorn"
    obs_stub.query = "what news"

    arm_profile: Any = MagicMock()
    arm_profile.skip_rag = True
    arm_profile.enabled_tiers = []

    with (
        patch("arm_probe.gate_2_corpus") as mock_g2,
        patch("arm_probe.gate_4_effect") as mock_g4,
        patch("arm_probe.corpus_fields", new=MagicMock()),
        patch("arm_probe._observe_all", return_value=([obs_stub], {"wide_rag": [obs_stub]})),
        patch("arm_probe.print_observations"),
    ):
        mock_g2.return_value = _PASS2
        mock_g4.return_value = _PASS2
        results = _live_gates(
            MagicMock(), arms={"wide_rag": arm_profile}, player_id="p1", selected="all"
        )

    mock_g4.assert_called_once()
    assert len(results) == 2


def test_live_gates_gate2_only_when_selected_2() -> None:
    """--gate 2 exercises gate 2; the result list has exactly one entry."""
    with (
        patch("arm_probe.gate_2_corpus") as mock_g2,
        patch("arm_probe.gate_4_effect"),
        patch("arm_probe.corpus_fields", new=MagicMock()),
    ):
        mock_g2.return_value = _PASS2
        results = _live_gates(MagicMock(), arms={}, player_id="p1", selected="2")

    mock_g2.assert_called_once()
    assert len(results) == 1


# ---------------------------------------------------------------------------
# _run — gate-1 early exit and live-gate dispatch
# ---------------------------------------------------------------------------


def test_run_gate1_failure_exits_before_live_phase(capsys: pytest.CaptureFixture[str]) -> None:
    """Gate 1 failing before the live phase produces exit code 1 from gate 1 alone."""
    with (
        patch("arm_probe._declared_arms", return_value={}),
        patch("arm_probe.gate_1_config") as mock_g1,
    ):
        mock_g1.return_value = _FAIL
        code = _run("http://localhost", "key", "p1", "all")

    mock_g1.assert_called_once()
    assert code == 1


def test_run_failing_gate_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    """A failing gate flows through _finish and produces exit code 1 with FAILED output."""
    with (
        patch("arm_probe._declared_arms", return_value={}),
        patch("arm_probe.gate_1_config", return_value=_FAIL),
    ):
        code = _run("http://localhost", "key", "p1", "all")

    out = capsys.readouterr().out
    assert code == 1
    assert "RESULT: FAILED" in out


def test_run_all_gates_pass_returns_0(capsys: pytest.CaptureFixture[str]) -> None:
    """Passing all selected gates produces exit code 0."""
    pass_gate3 = GateResult(number=3, name="isolation", passed=True, detail=())

    with (
        patch("arm_probe._declared_arms", return_value={}),
        patch("arm_probe.gate_1_config", return_value=_PASS),
        patch("arm_probe.gate_3_isolation", return_value=pass_gate3),
        patch("arm_probe._live_gates", return_value=[_PASS2]),
        patch("arm_probe.ProbeClient") as mock_pc,
    ):
        mock_pc.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_pc.return_value.__exit__ = MagicMock(return_value=False)
        code = _run("http://localhost", "key", "p1", "all")

    assert code == 0


def test_run_gate3_failure_in_all_mode_exits_before_live_phase(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failing gate 3 in 'all' mode stops before the ProbeClient is opened."""
    fail3 = GateResult(number=3, name="isolation", passed=False, detail=("collision",))
    with (
        patch("arm_probe._declared_arms", return_value={}),
        patch("arm_probe.gate_1_config", return_value=_PASS),
        patch("arm_probe.gate_3_isolation") as mock_g3,
    ):
        mock_g3.return_value = fail3
        code = _run("http://localhost", "key", "p1", "all")

    mock_g3.assert_called_once()
    assert code == 1
    out = capsys.readouterr().out
    assert "FAILED" in out


# ---------------------------------------------------------------------------
# _observe_all — client calls per case
# ---------------------------------------------------------------------------


def test_observe_all_returns_one_default_and_one_arm_entry() -> None:
    """Calls client.observe for every PROBE_CASES entry, for default and for each arm."""
    from arm_probe import PROBE_CASES

    obs = ArmObservation(
        arm="default", npc_id="captain_sorn", query="what news",
        item_keys=(), tier_spend=(), total_tokens=0,
    )
    mock_client = MagicMock()
    mock_client.observe.return_value = obs

    defaults, arm_runs = _observe_all(mock_client, {"wide_rag": MagicMock()}, "p1")

    assert len(defaults) == len(PROBE_CASES)
    assert "wide_rag" in arm_runs
    assert len(arm_runs["wide_rag"]) == len(PROBE_CASES)


# ---------------------------------------------------------------------------
# _declared_arms — engine_adapter integration
# ---------------------------------------------------------------------------


def test_declared_arms_returns_dict_keyed_by_profile_name() -> None:
    """_declared_arms imports engine_adapter and returns resolved profiles by name."""
    mock_engine = MagicMock()
    mock_engine.declared_retrieval_profiles.return_value = ["arm1", "arm2"]
    mock_engine.resolve_retrieval_profile.side_effect = lambda name: {"id": name}

    with patch.dict("sys.modules", {"engine_adapter": mock_engine}):
        result = _declared_arms()

    assert set(result.keys()) == {"arm1", "arm2"}
    mock_engine.declared_retrieval_profiles.assert_called_once()


# ---------------------------------------------------------------------------
# main — argv parsing and api-key guard
# ---------------------------------------------------------------------------


def test_main_returns_1_without_api_key_for_live_gates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without API_KEY_SECRET, gates 2 and 4 cannot run; main must exit 1 immediately."""
    env_clean = {k: v for k, v in os.environ.items() if k != "API_KEY_SECRET"}
    with patch.dict(os.environ, env_clean, clear=True):
        code = main(argv=["--gate", "all"])
    out = capsys.readouterr().out
    assert code == 1
    assert "API_KEY_SECRET" in out


def test_main_forwards_gate_selection_to_run() -> None:
    """--gate 1 is forwarded to _run as selected='1'; _run is the only entry point."""
    with (
        patch("arm_probe._run") as mock_run,
        patch.dict(os.environ, {"API_KEY_SECRET": ""}, clear=False),
    ):
        mock_run.return_value = 0
        code = main(argv=["--gate", "1"])

    mock_run.assert_called_once()
    assert mock_run.call_args[0][3] == "1"
    assert code == 0
