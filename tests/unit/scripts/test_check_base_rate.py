"""
Module: tests.unit.scripts.test_check_base_rate
Layer: tests
Purpose: Unit tests for scripts/check_base_rate.py — the EVAL-P25.3 base-rate
         contract. A battery whose pass rate sits on the ceiling inflates Pe and
         suppresses kappa, so the case set has a declared target band and this
         gate measures a generation directory against it.
Dependencies: json, pathlib, sys, pytest, check_base_rate
Used by: make test / make check (pytest discovery)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_base_rate import (  # noqa: E402
    ADVISORY,
    BLOCKING,
    TARGET_BAND_HIGH,
    TARGET_BAND_LOW,
    BandStatus,
    BaseRateReport,
    EmptyGenerationError,
    check_generation,
    format_report,
    smallest_n_reaching_band,
)

#: The committed generation the plan names as the RED anchor: measured 0.949 overall,
#: which is far above TARGET_BAND_HIGH and is exactly the defect P25.3 exists to name.
_ANCHOR_GEN = REPO_ROOT / "evals" / "generations" / "k3_77688e7_regen1"


def _write_gen(tmp_path: Path, deterministic: list[dict], judged: list[dict] | None = None) -> Path:
    """Write a minimal generation directory holding the two verdict files."""
    gen = tmp_path / "gen_under_test"
    gen.mkdir()
    (gen / "deterministic_judged.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in deterministic), encoding="utf-8"
    )
    if judged is not None:
        (gen / "judged.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in judged), encoding="utf-8"
        )
    return gen


def _det(kind: str, passed: bool, index: int) -> dict:
    """One deterministic_judged.jsonl row."""
    return {
        "record_id": f"case_x:{kind}:{index}",
        "repetition": 0,
        "matcher_kind": kind,
        "passed": passed,
        "score": passed,
        "reasoning": "",
    }


# ---------------------------------------------------------------------------
# RED anchor — the committed 0.949 generation must report out of band
# ---------------------------------------------------------------------------


def test_the_shipped_generation_reports_out_of_band() -> None:
    """EVAL-P25.3's RED anchor: k3_77688e7_regen1 measures 0.949 and is ABOVE the band.

    This is the whole point of the phase. If this ever reads in_band without the
    case set having been rebuilt, the gate has been weakened, not satisfied.
    """
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)

    # Both verdict files are read: 630 deterministic rows + 345 judged rows.
    assert report.overall.n == 975
    assert report.overall.pass_rate == pytest.approx(0.9426, abs=5e-4)
    assert report.overall.status is BandStatus.ABOVE_BAND


def test_the_deterministic_subset_reproduces_the_planned_ground_truth() -> None:
    """The plan's measured deterministic table: n=630 at 0.949. Reproduce it exactly.

    Guards against a silent change in how families are counted: if this drifts, the
    number every downstream MDE and kappa argument rests on has drifted with it.
    """
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    deterministic = {
        "schema", "min_length", "keyword_any", "keyword_none",
        "in_set", "range", "anti_hallucination_grounded",
    }
    rows = [f for f in report.families if f.family in deterministic]

    assert sum(f.n for f in rows) == 630
    assert sum(f.passes for f in rows) / 630 == pytest.approx(0.9492, abs=5e-4)
    assert {f.family: round(f.pass_rate, 3) for f in rows} == {
        "keyword_none": 0.957,
        "schema": 1.0,
        "min_length": 1.0,
        "keyword_any": 0.647,
        "anti_hallucination_grounded": 0.896,
        "in_set": 1.0,
        "range": 1.0,
    }


def test_the_shipped_generation_names_its_four_constant_families() -> None:
    """Four of seven matcher families are constant — zero variance, nothing to move."""
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    constant = sorted(f.family for f in report.families if not f.has_variance)

    assert constant == ["in_set", "min_length", "range", "schema"]


def test_the_shipped_generation_puts_only_keyword_any_in_band() -> None:
    """keyword_any at 0.647 is the one family already inside the target band."""
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    in_band = sorted(f.family for f in report.families if f.status is BandStatus.IN_BAND)

    assert in_band == ["keyword_any"]


# ---------------------------------------------------------------------------
# The enforcement switch — advisory first, blocking only once EVAL-P26 lands
# ---------------------------------------------------------------------------


def test_advisory_mode_reports_the_breach_but_does_not_block() -> None:
    """First-run contract: report the number, exit clean. Today's set fails by construction."""
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)

    assert report.breaches, "advisory mode must still name the out-of-band families"
    assert report.exit_code == 0


def test_blocking_mode_fails_on_the_same_report() -> None:
    """Once EVAL-P26 lands the same measurement becomes a gate. Same data, different verdict."""
    report = check_generation(_ANCHOR_GEN, enforcement=BLOCKING)

    assert report.breaches
    assert report.exit_code == 1


def test_blocking_mode_passes_a_generation_inside_the_band(tmp_path: Path) -> None:
    """A set with a real base rate clears the gate in blocking mode: 7/10 = 0.70."""
    gen = _write_gen(tmp_path, [_det("keyword_any", i < 7, i) for i in range(10)])
    report = check_generation(gen, enforcement=BLOCKING)

    assert report.overall.status is BandStatus.IN_BAND
    assert not report.breaches
    assert report.exit_code == 0


# ---------------------------------------------------------------------------
# Band arithmetic — the minimum n is derived from the band, not invented
# ---------------------------------------------------------------------------


def test_smallest_n_reaching_band_is_derived_not_hardcoded() -> None:
    """With band [0.55, 0.85] no rate k/n lands inside until n == 3 (2/3 = 0.667).

    DEC-181 rejected an uncalibrated free parameter. The minimum-n below which a
    family gets no band verdict is therefore computed from the band itself.
    """
    assert smallest_n_reaching_band(TARGET_BAND_LOW, TARGET_BAND_HIGH) == 3
    assert smallest_n_reaching_band(0.99, 0.995) == 100  # 99/100 = 0.99, the low edge


def test_a_family_below_the_minimum_n_gets_no_band_verdict(tmp_path: Path) -> None:
    """n=2 can only ever produce 0.0, 0.5 or 1.0 — none in band. Do not call that a breach."""
    gen = _write_gen(tmp_path, [_det("range", True, 0), _det("range", False, 1)])
    report = check_generation(gen, enforcement=BLOCKING)
    family = next(f for f in report.families if f.family == "range")

    assert family.status is BandStatus.INSUFFICIENT_N
    assert family.family not in {b.family for b in report.breaches}


# ---------------------------------------------------------------------------
# Grouping and inputs
# ---------------------------------------------------------------------------


def test_judged_rows_group_by_judge_kind(tmp_path: Path) -> None:
    """The grouping key is the matcher/expectation kind, across both verdict files."""
    gen = _write_gen(
        tmp_path,
        [_det("keyword_any", True, i) for i in range(4)],
        judged=[
            {"record_id": f"case_x:tone_judge:{i}", "judge_kind": "tone_judge", "passed": i < 3}
            for i in range(4)
        ],
    )
    report = check_generation(gen, enforcement=ADVISORY)

    assert sorted(f.family for f in report.families) == ["keyword_any", "tone_judge"]
    assert report.overall.n == 8


def test_an_empty_generation_directory_raises(tmp_path: Path) -> None:
    """No verdict rows is not a passing base rate — it is an unmeasured one."""
    empty = tmp_path / "empty_gen"
    empty.mkdir()

    with pytest.raises(EmptyGenerationError):
        check_generation(empty, enforcement=ADVISORY)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def test_report_names_the_band_the_mode_and_every_breach() -> None:
    """The advisory run's whole value is the report, so assert it carries the facts."""
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    text = format_report(report)

    assert "0.55" in text and "0.85" in text
    assert ADVISORY in text
    assert "keyword_none" in text
    assert isinstance(report, BaseRateReport)
