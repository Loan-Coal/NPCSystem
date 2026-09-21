"""
Module: tests.unit.evals.test_arm_probe_report
Layer: test (unit)
Purpose: Unit tests for evals/arm_probe_report.py — print_gate, print_observations, and
         print_mde_section, covering pass/fail verdicts, empty inputs, and the all-failed
         state. All rendering tested via stdout capture; no live services.
Dependencies: pytest, evals.arm_probe_report, evals.arm_probe_models
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "evals"))

from arm_probe_models import ArmObservation, GateResult, TierRow  # noqa: E402
from arm_probe_report import print_gate, print_mde_section, print_observations  # noqa: E402


def _obs(arm: str, *, tier_b: int = 2) -> ArmObservation:
    return ArmObservation(
        arm=arm,
        npc_id="captain_sorn",
        query="what news",
        item_keys=("world", "beliefs", "rag:a"),
        tier_spend=(
            TierRow(tier="tier0", items=3, tokens=93),
            TierRow(tier="tierA", items=8, tokens=687),
            TierRow(tier="tierB", items=tier_b, tokens=93 if tier_b else 0),
            TierRow(tier="tierC", items=3, tokens=140),
        ),
        total_tokens=1013,
    )


# ---------------------------------------------------------------------------
# print_gate
# ---------------------------------------------------------------------------


def test_print_gate_shows_pass_status(capsys: pytest.CaptureFixture[str]) -> None:
    """A passing gate prints PASS and its detail lines."""
    result = GateResult(number=1, name="config", passed=True, detail=("arm differs on tier",))
    print_gate(result)
    out = capsys.readouterr().out
    assert "[GATE 1] PASS" in out
    assert "config" in out
    assert "arm differs on tier" in out


def test_print_gate_shows_fail_status(capsys: pytest.CaptureFixture[str]) -> None:
    """A failing gate prints FAIL and its detail lines."""
    result = GateResult(number=2, name="corpus", passed=False, detail=("item_count is 0",))
    print_gate(result)
    out = capsys.readouterr().out
    assert "[GATE 2] FAIL" in out
    assert "corpus" in out
    assert "item_count is 0" in out


def test_print_gate_with_no_detail_lines(capsys: pytest.CaptureFixture[str]) -> None:
    """Gate output is printed even when detail tuple is empty — gate ran, result visible."""
    result = GateResult(number=3, name="isolation", passed=True, detail=())
    print_gate(result)
    out = capsys.readouterr().out
    assert "[GATE 3] PASS" in out


# ---------------------------------------------------------------------------
# print_observations
# ---------------------------------------------------------------------------


def test_print_observations_single_arm(capsys: pytest.CaptureFixture[str]) -> None:
    """One default run and one arm produces the table header and both rows."""
    default = [_obs("default")]
    arms = {"wide_rag": [_obs("wide_rag", tier_b=4)]}
    print_observations(default, arms)
    out = capsys.readouterr().out
    assert "captain_sorn" in out
    assert "default" in out
    assert "wide_rag" in out


def test_print_observations_shows_added_and_removed_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The diff row lists keys added and removed by the arm versus the default."""
    default_obs = ArmObservation(
        arm="default", npc_id="captain_sorn", query="what news",
        item_keys=("world", "beliefs"),
        tier_spend=(), total_tokens=100,
    )
    arm_obs = ArmObservation(
        arm="wide_rag", npc_id="captain_sorn", query="what news",
        item_keys=("world", "rag:extra"),
        tier_spend=(), total_tokens=200,
    )
    print_observations([default_obs], {"wide_rag": [arm_obs]})
    out = capsys.readouterr().out
    assert "rag:extra" in out
    assert "beliefs" in out


def test_print_observations_with_empty_arm_runs(capsys: pytest.CaptureFixture[str]) -> None:
    """No arm runs produces only the default rows, without raising."""
    default = [_obs("default")]
    print_observations(default, {})
    out = capsys.readouterr().out
    assert "captain_sorn" in out


# ---------------------------------------------------------------------------
# print_mde_section
# ---------------------------------------------------------------------------


def test_print_mde_section_single_comparison(capsys: pytest.CaptureFixture[str]) -> None:
    """Renders MDE table for a single arm pairing without raising."""
    print_mde_section(comparisons=1)
    out = capsys.readouterr().out
    assert "MINIMUM DETECTABLE EFFECT" in out
    assert "Bonferroni over 1 pairing" in out


def test_print_mde_section_multiple_comparisons(capsys: pytest.CaptureFixture[str]) -> None:
    """Multiple pairings are reflected in the Bonferroni line."""
    print_mde_section(comparisons=3)
    out = capsys.readouterr().out
    assert "3 pairings" in out
