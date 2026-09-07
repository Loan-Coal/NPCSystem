"""
Module: check_base_rate
Layer: scripts (dev tooling — imports evals/ only, never src/)
Purpose: EVAL-P25.3. Measure a generation directory's pass base rate, overall and per
         matcher/expectation family, against the target band declared in
         docs/CASE_SET_POLICY.md. A case every NPC passes is not a measurement: kappa is
         chance-corrected, so a base rate on the ceiling inflates Pe and suppresses kappa
         even at high raw agreement (affirms_judge: 130/135 raw = 96.3%, kappa 0.530).
         This script turns that fact into a checkable contract.
Dependencies: argparse, json, pathlib, sys, typing; scripts/base_rate_contract.
Used by: `make check-base-rate`, tests/unit/scripts/test_check_base_rate.py.

Enforcement is a first-class, documented parameter, not a commented-out line. The band
cannot bind the CURRENT battery — `k3_77688e7_regen1` measures 0.943 overall with nine
of ten families out of band — so raw `blocking` would red on day one for a defect no
scheduled task fixes. The shipped mode is `ratchet` (R2.3): the current measurement is
recorded in scripts/base_rate_baseline.json and the gate reds when the overall rate RISES
above it, or when a family enters a breach the baseline did not record. Debt can shrink,
never grow. Re-record with --update, deliberately, after an intentional improvement.

`advisory` remains available for exploration but is no longer the default: its promotion
criterion named EVAL-P26, a phase DEC-233 culled, so it would never have fired.

This module reads committed artifacts and never writes to them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

from base_rate_contract import (
    ADVISORY,
    BLOCKING,
    DEFAULT_ENFORCEMENT,
    ENFORCEMENT_MODES,
    RATCHET,
    TARGET_BAND_HIGH,
    TARGET_BAND_LOW,
    BandStatus,
    BaseRateBaseline,
    BaseRateReport,
    EmptyGenerationError,
    FamilyRate,
    classify,
    smallest_n_reaching_band,
)

#: Re-exported so the whole gate is importable from one module.
__all__ = [
    "ADVISORY", "BASELINE_PATH", "BLOCKING", "DEFAULT_ENFORCEMENT", "ENFORCEMENT_MODES",
    "RATCHET", "TARGET_BAND_HIGH", "TARGET_BAND_LOW", "BandStatus", "BaseRateBaseline",
    "BaseRateReport", "EmptyGenerationError", "FamilyRate", "check_generation", "classify",
    "format_report", "main", "read_baseline", "regressions_vs_baseline",
    "smallest_n_reaching_band", "write_baseline",
]

#: Verdict files inside a generation directory, and the field naming the family in each.
#: Both are read: judged.jsonl covers only the three LLM judges (~38% of records), and a
#: base rate over that subset alone would miss all four constant matcher families.
_VERDICT_FILES: tuple[tuple[str, str], ...] = (
    ("deterministic_judged.jsonl", "matcher_kind"),
    ("judged.jsonl", "judge_kind"),
)

#: Families excluded from the base-rate measurement itself (measurement-remediation
#: Phase 2, DEC-269), not just reported separately — a family with zero (or
#: structurally-suppressed) variance cannot move under any A/B change and cannot
#: meaningfully enter a breach, so counting its rows in `ALL` only pushes the overall
#: rate toward its own ceiling and crushes every OTHER family's kappa the same way
#: affirms_judge's already is (line 8).
#:   schema/min_length/in_set/range: measured at exactly 1.000 (zero variance) in every
#:   recorded generation — `docs/CASE_SET_POLICY.md`'s base-rate-contract table: schema
#:   n=186, min_length n=111, in_set n=18, range n=9. These are response-shape validators
#:   (matchers.py's `_eval_schema`/`_eval_min_length`/`_eval_in_set`/`_eval_range`), not
#:   scorers, and none ever carried a Cohen's kappa (BATTERY_JUDGED_SCORERS already
#:   excludes purely mechanical matchers — see evals/battery_trust.py).
#:   liveness_judge: the guard battery's auto-injected liveness check (formerly
#:   mislabelled `tone_judge` — see guard_expectations.GUARD_LIVENESS_RUBRIC), which
#:   fails on four narrow structural conditions only and cannot produce a content
#:   verdict by design. Was the dominant contributor to tone_judge's real (authored)
#:   signal being crushed to kappa 0.003 before the Phase 2b split.
#: This does not change what a case reports: runner.py's per-expectation gating is
#: unchanged, so a failure in any of these still fails its case exactly as before.
#: Only this gate's tally changes.
_STRUCTURAL_FAMILIES: frozenset[str] = frozenset(
    {"schema", "min_length", "in_set", "range", "liveness_judge"}
)

_OVERALL_FAMILY: str = "ALL"

#: The two statuses that count as a breach.
_OUT_OF_BAND: tuple[BandStatus, ...] = (BandStatus.ABOVE_BAND, BandStatus.BELOW_BAND)

#: Recorded measurement the ratchet judges against. A single integer would not do:
#: the breach SET matters as much as the scalar, so this is JSON.
BASELINE_PATH: Path = Path(__file__).resolve().parent / "base_rate_baseline.json"


class MissingBaselineError(ValueError):
    """Raised when a baseline file exists but cannot be parsed.

    Falling back to "no baseline" would read as green, which is exactly the silent
    degradation this gate exists to prevent.
    """


# --- Loading ---


def _iter_rows(gen_dir: Path) -> Iterable[tuple[str, bool]]:
    """Yield (family, passed) for every scored row in a generation directory.

    Rows whose family is in `_STRUCTURAL_FAMILIES` are excluded — see that constant's
    docstring for why a zero-variance family has no place in a base-rate measurement.
    """
    for filename, family_field in _VERDICT_FILES:
        path = gen_dir / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            row: dict[str, Any] = json.loads(stripped)
            family = row.get(family_field)
            if family is not None and str(family) not in _STRUCTURAL_FAMILIES:
                yield str(family), bool(row.get("passed", False))


def _tally(gen_dir: Path) -> dict[str, list[int]]:
    """Group rows by family into {family: [passes, n]}.

    Raises:
        EmptyGenerationError: When no row carried a family field.
    """
    groups: dict[str, list[int]] = {}
    for family, passed in _iter_rows(gen_dir):
        bucket = groups.setdefault(family, [0, 0])
        bucket[0] += int(passed)
        bucket[1] += 1
    if not groups:
        raise EmptyGenerationError(
            f"no scored rows under {gen_dir}: expected at least one of "
            f"{', '.join(name for name, _ in _VERDICT_FILES)} with verdict rows"
        )
    return groups


def _rate(family: str, passes: int, n: int, low: float, high: float) -> FamilyRate:
    """Build one FamilyRate from a tally."""
    return FamilyRate(
        family=family,
        n=n,
        passes=passes,
        pass_rate=passes / n,
        status=classify(passes, n, low, high),
        has_variance=0 < passes < n,
    )


def _measure_families(gen_dir: Path, band_low: float, band_high: float) -> tuple[FamilyRate, ...]:
    """Tally one generation directory into per-family rates, largest n first."""
    return tuple(
        sorted(
            (_rate(name, p, n, band_low, band_high) for name, (p, n) in _tally(gen_dir).items()),
            key=lambda f: (-f.n, f.family),
        )
    )


# --- Baseline (ratchet) ---


def read_baseline(path: Path = BASELINE_PATH) -> BaseRateBaseline | None:
    """Load the recorded measurement, or None when no baseline has been recorded.

    Args:
        path: Baseline JSON file.
    Returns:
        The parsed baseline, or None when the file is absent.
    Raises:
        MissingBaselineError: When the file exists but is not a readable baseline. A
            corrupt baseline must not silently degrade to "no baseline", which reads as
            green — the failure mode this whole gate exists to stop.
    """
    if not path.exists():
        return None
    try:
        return BaseRateBaseline.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MissingBaselineError(f"baseline at {path} exists but could not be read: {exc!r}") from exc


def write_baseline(report: BaseRateReport, path: Path = BASELINE_PATH) -> BaseRateBaseline:
    """Record `report` as the new baseline and return it.

    Args:
        report: The measurement to record.
        path: Baseline JSON file to write.
    Returns:
        The baseline that was written.
    """
    baseline = BaseRateBaseline(
        gen_dir=Path(report.gen_dir).as_posix(),
        overall_rate=report.overall.pass_rate,
        overall_n=report.overall.n,
        breaches={f.family: f.status.value for f in report.breaches},
    )
    payload = baseline.model_dump_json(indent=2)
    path.write_text(f"{payload}\n", encoding="utf-8", newline="")
    return baseline


def _measurement_regressions(overall: FamilyRate, baseline: BaseRateBaseline) -> list[str]:
    """The two ways the whole-battery measurement itself can be worse: rate up, n down.

    A baseline with no recorded `overall_n` abstains from the denominator check rather
    than failing: those files predate the field and are legacy, not corrupt.
    """
    found: list[str] = []
    if overall.pass_rate > baseline.overall_rate:
        found.append(
            f"overall rate rose {baseline.overall_rate:.4f} -> {overall.pass_rate:.4f} "
            f"(higher is worse: the band is breached from above)"
        )
    if baseline.overall_n is not None and overall.n < baseline.overall_n:
        found.append(
            f"corpus shrank {baseline.overall_n} -> {overall.n} scored rows "
            f"(a rate over fewer rows is a different measurement, not a better one)"
        )
    return found


def regressions_vs_baseline(
    overall: FamilyRate,
    breaches: Sequence[FamilyRate],
    baseline: BaseRateBaseline | None,
) -> tuple[str, ...]:
    """Name every way this measurement is worse than the recorded one.

    Three things can regress: the whole-battery rate can rise (the band is breached from
    above, so higher is worse), the corpus can shrink (a rate is not a measurement without
    the denominator it was taken over — ISSUE-245), and a family can enter a breach the
    baseline did not record, including the same family breaching in the opposite direction.

    Args:
        overall: This run's whole-battery rate.
        breaches: This run's out-of-band families.
        baseline: The recorded measurement, or None when none has been recorded.
    Returns:
        Human-readable regression reasons; empty when the run is at or better than baseline.
    """
    if baseline is None:
        return (
            "no baseline recorded — run `make check-base-rate-update` to record the "
            "current measurement before this gate can ratchet",
        )
    found = _measurement_regressions(overall, baseline)
    found.extend(
        f"{f.family} newly {f.status.value} (baseline recorded {baseline.breaches.get(f.family, 'in band')})"
        for f in breaches
        if baseline.breaches.get(f.family) != f.status.value
    )
    return tuple(found)


# --- Public entry point ---


def check_generation(
    gen_dir: Path,
    *,
    enforcement: str = DEFAULT_ENFORCEMENT,
    band_low: float = TARGET_BAND_LOW,
    band_high: float = TARGET_BAND_HIGH,
    baseline: BaseRateBaseline | None = None,
) -> BaseRateReport:
    """Measure a generation directory's base rate against the target band.

    Args:
        gen_dir: A directory holding deterministic_judged.jsonl and/or judged.jsonl.
        enforcement: ADVISORY (report, exit 0), BLOCKING (exit 1 on any breach), or
            RATCHET (exit 1 only when worse than `baseline`).
        band_low: Inclusive lower band edge.
        band_high: Inclusive upper band edge.
        baseline: Recorded measurement for RATCHET mode; injected, not read here, so this
            function stays a pure measurement over its arguments.
    Returns:
        The BaseRateReport; `exit_code` carries the enforcement decision.
    Raises:
        EmptyGenerationError: When the directory holds no scored rows.
        ValueError: On an undeclared enforcement mode or an invalid band.
    """
    if enforcement not in ENFORCEMENT_MODES:
        raise ValueError(f"unknown enforcement mode {enforcement!r}; expected one of {ENFORCEMENT_MODES}")
    families = _measure_families(gen_dir, band_low, band_high)
    overall = _rate(
        _OVERALL_FAMILY, sum(f.passes for f in families), sum(f.n for f in families), band_low, band_high
    )
    return _build_report(gen_dir, families, overall, enforcement, band_low, band_high, baseline)


def _build_report(
    gen_dir: Path,
    families: tuple[FamilyRate, ...],
    overall: FamilyRate,
    enforcement: str,
    band_low: float,
    band_high: float,
    baseline: BaseRateBaseline | None,
) -> BaseRateReport:
    """Assemble the report, deriving the breach list and (in ratchet mode) regressions."""
    breaches = tuple(f for f in families if f.status in _OUT_OF_BAND)
    return BaseRateReport(
        gen_dir=str(gen_dir),
        band_low=band_low,
        band_high=band_high,
        enforcement=enforcement,
        overall=overall,
        families=families,
        breaches=breaches,
        baseline=baseline,
        regressions=regressions_vs_baseline(overall, breaches, baseline)
        if enforcement == RATCHET
        else (),
    )


# --- Report ---


def _family_line(rate: FamilyRate) -> str:
    """One family row for the report table."""
    variance = "" if rate.has_variance else "  <- CONSTANT: no variance to move"
    return f"  {rate.family:<28} n={rate.n:>5}  rate={rate.pass_rate:.3f}  {rate.status.value}{variance}"


def format_report(report: BaseRateReport) -> str:
    """Render the measurement, the band, the mode, and every breach.

    Args:
        report: The measurement to render.
    Returns:
        A multi-line report. Advisory mode prints the breach list in full and still
        exits 0 — see the module docstring.
    """
    lines = [
        f"base-rate contract vs {report.gen_dir}",
        f"  target band: [{report.band_low:.2f}, {report.band_high:.2f}]   mode: {report.enforcement}",
        _family_line(report.overall),
        "  --",
    ]
    lines.extend(_family_line(f) for f in report.families)
    if report.breaches:
        lines.append("  out of band:")
        lines.extend(f"    - {f.family} ({f.pass_rate:.3f}, {f.status.value})" for f in report.breaches)
        if report.enforcement == ADVISORY:
            lines.append("  ADVISORY: reported, not blocking. Exploration mode, not the shipped default.")
    else:
        lines.append("  every family with sufficient n is inside the band.")
    if report.enforcement == RATCHET:
        lines.extend(_ratchet_lines(report))
    return "\n".join(lines)


def _ratchet_lines(report: BaseRateReport) -> list[str]:
    """Render the ratchet verdict: what the baseline was, and how this run compares."""
    if report.regressions:
        return ["  RATCHET RED - this measurement is worse than the recorded baseline:"] + [
            f"    - {reason}" for reason in report.regressions
        ]
    baseline = report.baseline
    if baseline is None:
        return ["  RATCHET OK - no baseline to compare against."]
    recorded_n = "n not recorded" if baseline.overall_n is None else f"n={baseline.overall_n}"
    lines = [
        f"  RATCHET OK - at or better than baseline {baseline.overall_rate:.4f} "
        f"({recorded_n}, {len(baseline.breaches)} breaching families) from {baseline.gen_dir}."
    ]
    if report.overall.pass_rate < baseline.overall_rate or len(report.breaches) < len(baseline.breaches):
        lines.append("  Improved - re-record with `make check-base-rate-update` to lock the gain in.")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Measure one generation directory and exit per the enforcement mode."""
    parser = argparse.ArgumentParser(description="Gate a generation's pass base rate against the target band.")
    parser.add_argument("gen_dir", type=Path, help="generation directory to measure")
    parser.add_argument(
        "--enforce",
        choices=ENFORCEMENT_MODES,
        default=DEFAULT_ENFORCEMENT,
        help="advisory reports and exits 0; blocking exits 1 on any breach; ratchet exits 1 only when worse than the recorded baseline (default: %(default)s)",
    )
    parser.add_argument("--band-low", type=float, default=TARGET_BAND_LOW, help="inclusive lower band edge")
    parser.add_argument("--band-high", type=float, default=TARGET_BAND_HIGH, help="inclusive upper band edge")
    parser.add_argument("--baseline-file", type=Path, default=BASELINE_PATH, help="ratchet baseline JSON")
    parser.add_argument("--update", action="store_true", help="record this measurement as the baseline")
    args = parser.parse_args(argv)

    report = check_generation(
        args.gen_dir,
        enforcement=args.enforce,
        band_low=args.band_low,
        band_high=args.band_high,
        baseline=None if args.update else read_baseline(args.baseline_file),
    )
    if args.update:
        recorded = write_baseline(report, args.baseline_file)
        sys.stdout.write(
            f"check-base-rate: baseline recorded at {recorded.overall_rate:.4f} "
            f"with {len(recorded.breaches)} breaching families from {recorded.gen_dir}\n"
        )
        return 0
    sys.stdout.write(format_report(report) + "\n")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
