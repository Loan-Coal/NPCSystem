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
    BASELINE_PATH,
    BLOCKING,
    RATCHET,
    BaseRateBaseline,
    MissingBaselineError,
    TARGET_BAND_HIGH,
    TARGET_BAND_LOW,
    BandStatus,
    BaseRateReport,
    EmptyGenerationError,
    check_generation,
    format_report,
    main,
    read_baseline,
    regressions_vs_baseline,
    smallest_n_reaching_band,
    write_baseline,
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
    """EVAL-P25.3's RED anchor: k3_77688e7_regen1 measures 0.914 and is ABOVE the band.

    This is the whole point of the phase. If this ever reads in_band without the
    case set having been rebuilt, the gate has been weakened, not satisfied.

    n=651 and rate=0.914, not the pre-Phase-2a 975/0.9426 — measurement-remediation
    Phase 2a (DEC-269) excludes the four constant families (schema, min_length, in_set,
    range; 324 rows, all passing) from this measurement entirely: a family with zero
    variance cannot enter a breach and cannot be moved by any A/B change, so counting its
    rows only pushes the overall rate toward its own ceiling. See
    scripts/check_base_rate.py's `_STRUCTURAL_FAMILIES` docstring for the full reasoning.
    """
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)

    # Both verdict files are read: 345 judged rows + (630 deterministic - 324 excluded
    # structural) = 306 deterministic rows counted.
    assert report.overall.n == 651
    assert report.overall.pass_rate == pytest.approx(0.9140, abs=5e-4)
    assert report.overall.status is BandStatus.ABOVE_BAND


def test_the_deterministic_subset_reproduces_the_planned_ground_truth() -> None:
    """The post-Phase-2a deterministic table: n=306 at 0.895. Reproduce it exactly.

    Guards against a silent change in how families are counted: if this drifts, the
    number every downstream MDE and kappa argument rests on has drifted with it.
    schema/min_length/in_set/range are deliberately absent — see
    test_structural_families_never_appear_in_the_report below for that half of the
    contract.
    """
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    deterministic = {"keyword_any", "keyword_none", "anti_hallucination_grounded"}
    rows = [f for f in report.families if f.family in deterministic]

    assert sum(f.n for f in rows) == 306
    assert sum(f.passes for f in rows) / 306 == pytest.approx(0.8954, abs=5e-4)
    assert {f.family: round(f.pass_rate, 3) for f in rows} == {
        "keyword_none": 0.957,
        "keyword_any": 0.647,
        "anti_hallucination_grounded": 0.896,
    }


def test_structural_families_never_appear_in_the_report() -> None:
    """schema/min_length/in_set/range are excluded upstream, not merely reported as constant.

    Before Phase 2a these four were the "four constant families" — reported, and always
    at rate 1.0 with `has_variance=False`. Now they are absent from `report.families`
    entirely: `_iter_rows` filters them before any FamilyRate is ever built, so there is
    no family object here to assert `has_variance` on any more.
    """
    report = check_generation(_ANCHOR_GEN, enforcement=ADVISORY)
    families = {f.family for f in report.families}

    assert families.isdisjoint({"schema", "min_length", "in_set", "range"})


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
    """The same measurement as a hard gate. Same data, different verdict.

    Kept as a mode test. Blocking is NOT the shipped mode (R2.3 ships ratchet) — this
    asserts the mode works, not that it is in force.
    """
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
    gen = _write_gen(tmp_path, [_det("keyword_any", True, 0), _det("keyword_any", False, 1)])
    report = check_generation(gen, enforcement=BLOCKING)
    family = next(f for f in report.families if f.family == "keyword_any")

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


# ---------------------------------------------------------------------------
# R2.3: ratchet mode — the shipped enforcement
# ---------------------------------------------------------------------------


def _sub(tmp_path: Path, name: str) -> Path:
    """Create and return a named subdirectory (_write_gen needs an existing parent)."""
    path = tmp_path / name
    path.mkdir()
    return path


def _baseline_file(tmp_path: Path, gen: Path, enforcement: str = RATCHET) -> Path:
    """Record `gen`'s current measurement to a temp baseline file and return its path."""
    path = tmp_path / "baseline.json"
    write_baseline(check_generation(gen, enforcement=enforcement), path)
    return path


def test_ratchet_is_green_at_the_recorded_baseline(tmp_path: Path) -> None:
    """A measurement identical to the recorded one is not a regression."""
    gen = _write_gen(tmp_path, [_det("keyword_any", True, i) for i in range(20)])
    baseline = read_baseline(_baseline_file(tmp_path, gen))

    report = check_generation(gen, enforcement=RATCHET, baseline=baseline)

    assert report.breaches, "the fixture is deliberately out of band"
    assert report.regressions == ()
    assert report.exit_code == 0


def test_ratchet_reds_when_the_overall_rate_rises(tmp_path: Path) -> None:
    """Higher is worse: the band is breached from above, where Pe swamps kappa."""
    before = _write_gen(_sub(tmp_path, "a"), [_det("keyword_any", i < 7, i) for i in range(10)])
    baseline = read_baseline(_baseline_file(tmp_path, before))

    after = _write_gen(_sub(tmp_path, "b"), [_det("keyword_any", i < 9, i) for i in range(10)])
    report = check_generation(after, enforcement=RATCHET, baseline=baseline)

    assert report.exit_code == 1
    assert any("overall rate rose" in r for r in report.regressions)


def test_ratchet_reds_when_a_family_newly_enters_breach(tmp_path: Path) -> None:
    """A new all-passing family is a new guaranteed pass, even at an unchanged overall rate."""
    baseline = BaseRateBaseline(
        gen_dir="recorded",
        overall_rate=1.0,
        breaches={"keyword_any": "above_band"},
    )
    gen = _write_gen(
        tmp_path,
        [_det("keyword_any", True, i) for i in range(20)]
        + [_det("keyword_none", True, i) for i in range(20)],
    )

    report = check_generation(gen, enforcement=RATCHET, baseline=baseline)

    assert report.exit_code == 1
    assert any(r.startswith("keyword_none newly above_band") for r in report.regressions)


def test_ratchet_reds_when_the_corpus_shrinks_at_an_unchanged_rate(tmp_path: Path) -> None:
    """ISSUE-245: a rate is not a measurement without the denominator it was taken over.

    The recorded baseline carried `overall_rate` and `breaches` and no `n`, so a corpus
    that halved while holding its rate was indistinguishable from one that did not move
    at all. Deleting hard cases until the survivors agree is exactly how a battery
    reaches the ceiling this gate exists to detect, and it was the one route the ratchet
    could not see.

    Note the anchor is an UNCHANGED rate, not a higher one. A shrunken corpus at a HIGHER
    rate already reds on `overall rate rose` and so proves nothing about `n` — measured
    before this test was written: 20 rows at 0.70 -> 10 rows at 0.90 exits 1 today, while
    20 rows at 0.70 -> 10 rows at 0.70 exits 0.
    """
    before = _write_gen(_sub(tmp_path, "a"), [_det("keyword_any", i < 14, i) for i in range(20)])
    baseline = read_baseline(_baseline_file(tmp_path, before))

    after = _write_gen(_sub(tmp_path, "b"), [_det("keyword_any", i < 7, i) for i in range(10)])
    report = check_generation(after, enforcement=RATCHET, baseline=baseline)

    assert report.overall.pass_rate == baseline.overall_rate, "the fixture must hold the rate"
    assert report.exit_code == 1
    assert any("corpus shrank" in r for r in report.regressions)


def test_a_baseline_recorded_before_overall_n_reads_as_no_n_not_as_corrupt() -> None:
    """A legacy baseline must degrade to "n not recorded", never to a parse error.

    `read_baseline` raises on anything it cannot parse, and rightly so. But the three-key
    baselines written before this field existed are not corrupt, and turning every one of
    them into a hard failure would push people toward re-recording — which silently
    re-points the ratchet at whatever the corpus says today.
    """
    from check_base_rate import _rate  # noqa: PLC0415

    legacy = BaseRateBaseline.model_validate_json(
        '{"gen_dir": "g", "overall_rate": 0.5, "breaches": {}}'
    )
    shrunken = _rate("ALL", 5, 10, TARGET_BAND_LOW, TARGET_BAND_HIGH)

    assert legacy.overall_n is None
    assert regressions_vs_baseline(shrunken, (), legacy) == (), (
        "a baseline with no recorded n cannot judge a denominator"
    )


def test_ratchet_reds_when_no_baseline_is_recorded(tmp_path: Path) -> None:
    """An unrecorded baseline must red, not read as green — that is the silent-pass shape."""
    gen = _write_gen(tmp_path, [_det("keyword_any", True, i) for i in range(20)])

    report = check_generation(gen, enforcement=RATCHET, baseline=None)

    assert report.exit_code == 1
    assert any("no baseline recorded" in r for r in report.regressions)


def test_ratchet_is_green_when_the_rate_falls_and_says_to_re_record(tmp_path: Path) -> None:
    """Debt may shrink. The report then nudges toward locking the gain in."""
    before = _write_gen(_sub(tmp_path, "a"), [_det("keyword_any", True, i) for i in range(20)])
    baseline = read_baseline(_baseline_file(tmp_path, before))

    after = _write_gen(_sub(tmp_path, "b"), [_det("keyword_any", i < 14, i) for i in range(20)])
    report = check_generation(after, enforcement=RATCHET, baseline=baseline)

    assert report.exit_code == 0
    assert "re-record" in format_report(report)


def test_a_corrupt_baseline_raises_rather_than_reading_as_green(tmp_path: Path) -> None:
    """Unreadable must not degrade to "no baseline", which the caller would read as clean."""
    path = tmp_path / "baseline.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(MissingBaselineError):
        read_baseline(path)


def test_a_missing_baseline_file_reads_as_none(tmp_path: Path) -> None:
    """Absent is distinguishable from corrupt: absent returns None, corrupt raises."""
    assert read_baseline(tmp_path / "nope.json") is None


def test_regressions_are_empty_at_baseline_and_populated_above_it() -> None:
    """The regression helper is the whole ratchet decision — pin both directions."""
    from check_base_rate import _rate  # noqa: PLC0415

    baseline = BaseRateBaseline(gen_dir="g", overall_rate=0.90, breaches={"schema": "above_band"})
    same = _rate("ALL", 90, 100, TARGET_BAND_LOW, TARGET_BAND_HIGH)
    higher = _rate("ALL", 95, 100, TARGET_BAND_LOW, TARGET_BAND_HIGH)

    assert regressions_vs_baseline(same, (), baseline) == ()
    assert regressions_vs_baseline(higher, (), baseline) != ()


# ---------------------------------------------------------------------------
# The shipped gate: `make check-base-rate` must be green on a clean tree
# ---------------------------------------------------------------------------


def test_the_committed_baseline_is_green_against_the_committed_generation() -> None:
    """R2.3's halt condition, as a permanent test rather than a hand demonstration.

    If this ever reds on a clean tree, the baseline was recorded wrong or the mode logic
    is inverted. It must not be "fixed" by loosening the band or falling back to advisory.
    """
    assert BASELINE_PATH.exists(), "scripts/base_rate_baseline.json must be committed"
    report = check_generation(_ANCHOR_GEN, enforcement=RATCHET, baseline=read_baseline())

    assert report.regressions == ()
    assert report.exit_code == 0


def test_main_exits_zero_on_the_shipped_generation_and_baseline() -> None:
    """End to end through the CLI, which is what `make check-base-rate` actually runs."""
    assert main([str(_ANCHOR_GEN)]) == 0
