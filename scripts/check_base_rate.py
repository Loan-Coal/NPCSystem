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
cannot bind the CURRENT battery — it measures 0.949 and would fail by construction — so
the gate ships in `advisory` mode: it computes and reports the full breach list and exits
0, and is switched to `blocking` when EVAL-P26 has rebuilt the case set. Advisory is not
"disabled": the report and the breach list are identical in both modes and only
`exit_code` differs, so the switch to blocking is a formality rather than a surprise.

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
    TARGET_BAND_HIGH,
    TARGET_BAND_LOW,
    BandStatus,
    BaseRateReport,
    EmptyGenerationError,
    FamilyRate,
    classify,
    smallest_n_reaching_band,
)

#: Re-exported so the whole gate is importable from one module.
__all__ = [
    "ADVISORY", "BLOCKING", "DEFAULT_ENFORCEMENT", "ENFORCEMENT_MODES", "TARGET_BAND_HIGH",
    "TARGET_BAND_LOW", "BandStatus", "BaseRateReport", "EmptyGenerationError", "FamilyRate",
    "check_generation", "classify", "format_report", "main", "smallest_n_reaching_band",
]

#: Verdict files inside a generation directory, and the field naming the family in each.
#: Both are read: judged.jsonl covers only the three LLM judges (~38% of records), and a
#: base rate over that subset alone would miss all four constant matcher families.
_VERDICT_FILES: tuple[tuple[str, str], ...] = (
    ("deterministic_judged.jsonl", "matcher_kind"),
    ("judged.jsonl", "judge_kind"),
)

_OVERALL_FAMILY: str = "ALL"


# --- Loading ---


def _iter_rows(gen_dir: Path) -> Iterable[tuple[str, bool]]:
    """Yield (family, passed) for every scored row in a generation directory."""
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
            if family is not None:
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


# --- Public entry point ---


def check_generation(
    gen_dir: Path,
    *,
    enforcement: str = DEFAULT_ENFORCEMENT,
    band_low: float = TARGET_BAND_LOW,
    band_high: float = TARGET_BAND_HIGH,
) -> BaseRateReport:
    """Measure a generation directory's base rate against the target band.

    Args:
        gen_dir: A directory holding deterministic_judged.jsonl and/or judged.jsonl.
        enforcement: ADVISORY (report, exit 0) or BLOCKING (report, exit 1 on breach).
        band_low: Inclusive lower band edge.
        band_high: Inclusive upper band edge.
    Returns:
        The BaseRateReport; `exit_code` carries the enforcement decision.
    Raises:
        EmptyGenerationError: When the directory holds no scored rows.
        ValueError: On an undeclared enforcement mode or an invalid band.
    """
    if enforcement not in ENFORCEMENT_MODES:
        raise ValueError(f"unknown enforcement mode {enforcement!r}; expected one of {ENFORCEMENT_MODES}")
    families = tuple(
        sorted(
            (_rate(name, p, n, band_low, band_high) for name, (p, n) in _tally(gen_dir).items()),
            key=lambda f: (-f.n, f.family),
        )
    )
    out_of_band = (BandStatus.ABOVE_BAND, BandStatus.BELOW_BAND)
    return BaseRateReport(
        gen_dir=str(gen_dir),
        band_low=band_low,
        band_high=band_high,
        enforcement=enforcement,
        overall=_rate(
            _OVERALL_FAMILY, sum(f.passes for f in families), sum(f.n for f in families), band_low, band_high
        ),
        families=families,
        breaches=tuple(f for f in families if f.status in out_of_band),
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
            lines.append(f"  ADVISORY: reported, not blocking. Switch to {BLOCKING} when EVAL-P26 lands.")
    else:
        lines.append("  every family with sufficient n is inside the band.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Measure one generation directory and exit per the enforcement mode."""
    parser = argparse.ArgumentParser(description="Gate a generation's pass base rate against the target band.")
    parser.add_argument("gen_dir", type=Path, help="generation directory to measure")
    parser.add_argument(
        "--enforce",
        choices=ENFORCEMENT_MODES,
        default=DEFAULT_ENFORCEMENT,
        help="advisory reports and exits 0; blocking exits 1 on any breach (default: %(default)s)",
    )
    parser.add_argument("--band-low", type=float, default=TARGET_BAND_LOW, help="inclusive lower band edge")
    parser.add_argument("--band-high", type=float, default=TARGET_BAND_HIGH, help="inclusive upper band edge")
    args = parser.parse_args(argv)

    report = check_generation(
        args.gen_dir, enforcement=args.enforce, band_low=args.band_low, band_high=args.band_high
    )
    sys.stdout.write(format_report(report) + "\n")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
