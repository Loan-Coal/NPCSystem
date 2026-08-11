"""
Module: calibration
Layer: evals (eval harness — not part of src/)
Purpose: Per-scorer calibration reports with two confusion matrices each: a headline
         (scorer_verdict vs human_verdict) and a secondary (pre_label vs human_verdict),
         each with Cohen's κ and a seeded bootstrap CI. Prints one pair of matrices per
         scorer — never a single aggregate. Called by `make eval-calibrate`.
Dependencies: calibration_records, dataclasses, logging, math, random, pathlib, sys, typing
Used by: make eval-calibrate (CLI), tests/unit/evals/test_calibration.py
"""

from __future__ import annotations

import logging
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple, Sequence

from calibration_records import LABELS_FILE, CalibrationLabel, read_calibration_labels
from paired_stats import boundary_ci_note, is_boundary_ci

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOOTSTRAP_RESAMPLES: int = 2000
BOOTSTRAP_SEED: int = 42
CI_LO_PERCENTILE: float = 0.025
CI_HI_PERCENTILE: float = 0.975

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class KappaCI(NamedTuple):
    """Bootstrap confidence interval for Cohen's κ with cluster metadata.

    Attributes:
        lo: 2.5th-percentile bootstrap κ.
        hi: 97.5th-percentile bootstrap κ.
        n_clusters: Number of unique case clusters in the resampled population.
        n_rows: Total adjudicated rows (= sum of cluster sizes).
    """

    lo: float
    hi: float
    n_clusters: int
    n_rows: int


@dataclass(frozen=True)
class ConfusionCounts:
    """TP/FP/FN/TN for one scorer against human verdicts.

    FP is the dangerous cell: the scorer said "pass" but the human said "fail".
    """

    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def n(self) -> int:
        """Total adjudicated rows included in the matrix."""
        return self.tp + self.fp + self.fn + self.tn


@dataclass(frozen=True)
class ScorerReport:
    """Full calibration report for one scorer.

    counts / kappa / kappa_lo / kappa_hi are the HEADLINE axis:
        scorer_verdict vs human_verdict (can I trust this scorer?).
    pre_label_counts / pre_label_kappa / … are the SECONDARY axis:
        pre_label vs human_verdict (free reference-labeller agreement).
    kappa_n_clusters: case clusters used in the headline bootstrap CI.
    pre_label_n_clusters: case clusters used in the secondary bootstrap CI.
    """

    scorer: str
    counts: ConfusionCounts
    kappa: float
    kappa_lo: float
    kappa_hi: float
    kappa_n_clusters: int
    prec: float | None
    rec: float | None
    pre_label_agreement: float
    pre_label_counts: ConfusionCounts
    pre_label_kappa: float
    pre_label_kappa_lo: float
    pre_label_kappa_hi: float
    pre_label_n_clusters: int


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UndefinedKappaError(ValueError):
    """Raised when Pe≈1 makes κ = (Po−Pe)/(1−Pe) a 0/0 form.

    This occurs when both raters agree so completely that there is no variance
    in their outputs — Pe=1 means chance agreement equals observed agreement,
    making κ undefined rather than 1.0.

    Attributes:
        pe: Expected agreement probability that triggered the error.
        tp: True positive cell count.
        fp: False positive cell count.
        fn: False negative cell count.
        tn: True negative cell count.
    """

    def __init__(self, pe: float, tp: int, fp: int, fn: int, tn: int) -> None:
        self.pe = pe
        self.tp = tp
        self.fp = fp
        self.fn = fn
        self.tn = tn
        super().__init__(
            f"κ undefined: Pe={pe:.6f} ≈ 1 "
            f"(tp={tp}, fp={fp}, fn={fn}, tn={tn})"
        )


# ---------------------------------------------------------------------------
# Core computations
# ---------------------------------------------------------------------------


def confusion_counts(rows: Sequence[CalibrationLabel]) -> ConfusionCounts:
    """Tally TP/FP/FN/TN — HEADLINE axis: scorer_verdict vs human_verdict.

    FP = scorer_verdict=True, human_verdict=False — the dangerous cell
    (scorer said pass, human said fail).

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are skipped).
    Returns:
        ConfusionCounts from adjudicated rows only.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    tp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is False)
    return ConfusionCounts(tp=tp, fp=fp, fn=fn, tn=tn)


def pre_label_confusion_counts(rows: Sequence[CalibrationLabel]) -> ConfusionCounts:
    """Tally TP/FP/FN/TN — SECONDARY axis: pre_label vs human_verdict.

    FP = pre_label=True, human_verdict=False (reference labeller said pass,
    human said fail).

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are skipped).
    Returns:
        ConfusionCounts from adjudicated rows only.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    tp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is False)
    return ConfusionCounts(tp=tp, fp=fp, fn=fn, tn=tn)


def precision(counts: ConfusionCounts) -> float | None:
    """TP / (TP + FP). Returns None when no positives were predicted (TP+FP=0).

    Args:
        counts: ConfusionCounts from confusion_counts().
    Returns:
        Precision in [0, 1], or None when the denominator is zero.
    """
    denom = counts.tp + counts.fp
    return counts.tp / denom if denom > 0 else None


def recall(counts: ConfusionCounts) -> float | None:
    """TP / (TP + FN). Returns None when no ground-truth positives exist (TP+FN=0).

    Args:
        counts: ConfusionCounts from confusion_counts().
    Returns:
        Recall in [0, 1], or None when the denominator is zero.
    """
    denom = counts.tp + counts.fn
    return counts.tp / denom if denom > 0 else None


def _kappa_from_matrix(tp: int, fp: int, fn: int, tn: int) -> float:
    """Compute Cohen's κ from a 2×2 confusion matrix.

    Args:
        tp: True positives.
        fp: False positives.
        fn: False negatives.
        tn: True negatives.
    Returns:
        κ in [-1, 1].
    Raises:
        UndefinedKappaError: When Pe≈1, making κ = (Po−Pe)/(1−Pe) a 0/0 form.
    """
    n = tp + fp + fn + tn
    po = (tp + tn) / n
    p_yes_a = (tp + fp) / n
    p_yes_b = (tp + fn) / n
    p_no_a = (fn + tn) / n
    p_no_b = (fp + tn) / n
    pe = p_yes_a * p_yes_b + p_no_a * p_no_b
    if abs(1.0 - pe) < 1e-12:
        raise UndefinedKappaError(pe=pe, tp=tp, fp=fp, fn=fn, tn=tn)
    return (po - pe) / (1.0 - pe)


def cohens_kappa(rows: Sequence[CalibrationLabel]) -> float:
    """Cohen's κ — HEADLINE axis: scorer_verdict vs human_verdict.

    κ = (Po - Pe) / (1 - Pe). Only adjudicated rows are used.

    Args:
        rows: CalibrationLabel rows with human_verdict set.
    Returns:
        κ in [-1, 1].
    Raises:
        ValueError: If fewer than 2 adjudicated rows are available.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    if len(adj) < 2:
        raise ValueError(f"cohens_kappa requires ≥2 adjudicated rows; got {len(adj)}")
    tp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is False)
    return _kappa_from_matrix(tp, fp, fn, tn)


def pre_label_kappa(rows: Sequence[CalibrationLabel]) -> float:
    """Cohen's κ — SECONDARY axis: pre_label vs human_verdict.

    Args:
        rows: CalibrationLabel rows with human_verdict set.
    Returns:
        κ in [-1, 1].
    Raises:
        ValueError: If fewer than 2 adjudicated rows are available.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    if len(adj) < 2:
        raise ValueError(f"pre_label_kappa requires ≥2 adjudicated rows; got {len(adj)}")
    tp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is False)
    return _kappa_from_matrix(tp, fp, fn, tn)


def _extract_case_clusters(rows: list[CalibrationLabel]) -> list[list[CalibrationLabel]]:
    """Group rows by case_id (first ':'-delimited component of record_id).

    Preserves insertion order of first occurrence for stable iteration.

    Args:
        rows: Adjudicated CalibrationLabel rows.
    Returns:
        List of clusters; each cluster is all rows sharing the same case_id.
    """
    groups: dict[str, list[CalibrationLabel]] = {}
    for row in rows:
        case_id = row.record_id.split(":")[0]
        if case_id not in groups:
            groups[case_id] = []
        groups[case_id].append(row)
    return list(groups.values())


def _run_bootstrap_samples(
    clusters: list[list[CalibrationLabel]],
    kappa_fn: Callable[[list[CalibrationLabel]], float],
    resamples: int,
    rng: random.Random,
) -> tuple[list[float], int]:
    """Draw cluster bootstrap resamples; return (kappas, dropped_count).

    Each resample draws len(clusters) clusters with replacement, flattens to
    a row list, and calls kappa_fn. ValueError (degenerate Pe=1) increments
    dropped rather than aborting.
    """
    n = len(clusters)
    kappas: list[float] = []
    dropped = 0
    for _ in range(resamples):
        drawn = [clusters[rng.randrange(n)] for _ in range(n)]
        sample = [row for cluster in drawn for row in cluster]
        try:
            kappas.append(kappa_fn(sample))
        except ValueError:
            dropped += 1
    return kappas, dropped


def _bootstrap_percentile_ci(
    clusters: list[list[CalibrationLabel]],
    kappa_fn: Callable[[list[CalibrationLabel]], float],
    resamples: int,
    seed: int,
    caller: str,
) -> tuple[float, float, int, int]:
    """Run a seeded cluster bootstrap CI; return (lo, hi, n_clusters, n_rows).

    Args:
        clusters: Rows pre-grouped by case_id via _extract_case_clusters.
        kappa_fn: Computes κ from a list of CalibrationLabel; raises ValueError
            for degenerate (Pe=1) samples.
        resamples: Number of bootstrap samples.
        seed: RNG seed for reproducibility.
        caller: Used in log/error messages.
    Raises:
        ValueError: If all bootstrap samples were degenerate.
    """
    n_clusters = len(clusters)
    n_rows = sum(len(c) for c in clusters)
    kappas, dropped = _run_bootstrap_samples(clusters, kappa_fn, resamples, random.Random(seed))
    if dropped:
        _logger.warning(
            "%s: dropped %d of %d degenerate bootstrap samples (Pe=1) from CI",
            caller, dropped, resamples,
        )
    if not kappas:
        raise ValueError(f"{caller}: all {resamples} bootstrap samples were degenerate (Pe=1)")
    kappas.sort()
    total = len(kappas)
    lo_idx = math.floor(total * CI_LO_PERCENTILE)
    hi_idx = max(min(math.ceil(total * CI_HI_PERCENTILE) - 1, total - 1), lo_idx)
    return kappas[lo_idx], kappas[hi_idx], n_clusters, n_rows


def kappa_interval(
    rows: Sequence[CalibrationLabel],
    resamples: int,
    seed: int,
) -> KappaCI:
    """Bootstrap 95% CI on κ — HEADLINE axis (scorer_verdict vs human_verdict).

    Resamples by **case cluster** (all rows sharing the same case_id prefix move
    together), correcting for intra-case correlation from repeated generations.
    Same rows + seed always produce the same bounds.

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are ignored).
        resamples: Number of bootstrap resamples.
        seed: RNG seed — fix it to keep the interval reproducible.
    Returns:
        KappaCI with lo, hi (95% bootstrap CI), n_clusters, n_rows.
    Raises:
        ValueError: If fewer than 2 adjudicated rows or all samples degenerate.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    if len(adj) < 2:
        raise ValueError(f"kappa_interval requires ≥2 adjudicated rows; got {len(adj)}")
    clusters = _extract_case_clusters(adj)
    lo, hi, n_clusters, n_rows = _bootstrap_percentile_ci(
        clusters, cohens_kappa, resamples, seed, "kappa_interval"
    )
    return KappaCI(lo=lo, hi=hi, n_clusters=n_clusters, n_rows=n_rows)


def pre_label_kappa_interval(
    rows: Sequence[CalibrationLabel],
    resamples: int,
    seed: int,
) -> KappaCI:
    """Bootstrap 95% CI on κ — SECONDARY axis (pre_label vs human_verdict).

    Resamples by **case cluster** (same case-level correction as kappa_interval).

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are ignored).
        resamples: Number of bootstrap resamples.
        seed: RNG seed — fix it to keep the interval reproducible.
    Returns:
        KappaCI with lo, hi (95% bootstrap CI), n_clusters, n_rows.
    Raises:
        ValueError: If fewer than 2 adjudicated rows or all samples degenerate.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    if len(adj) < 2:
        raise ValueError(f"pre_label_kappa_interval requires ≥2 adjudicated rows; got {len(adj)}")
    clusters = _extract_case_clusters(adj)
    lo, hi, n_clusters, n_rows = _bootstrap_percentile_ci(
        clusters, pre_label_kappa, resamples, seed, "pre_label_kappa_interval"
    )
    return KappaCI(lo=lo, hi=hi, n_clusters=n_clusters, n_rows=n_rows)


def agreement_rate(rows: Sequence[CalibrationLabel]) -> float:
    """Fraction of adjudicated rows where pre_label == human_verdict.

    This is the free pre-label-vs-human agreement metric (DEC-153 §7).

    Args:
        rows: CalibrationLabel rows.
    Returns:
        Agreement fraction in [0, 1].
    Raises:
        ValueError: If no adjudicated rows exist.
    """
    adj = [r for r in rows if r.human_verdict is not None]
    if not adj:
        raise ValueError("agreement_rate requires at least 1 adjudicated row")
    agree = sum(1 for r in adj if r.pre_label == r.human_verdict)
    return agree / len(adj)


# ---------------------------------------------------------------------------
# Per-scorer report
# ---------------------------------------------------------------------------


def _pre_label_stats(
    scorer_rows: Sequence[CalibrationLabel],
) -> tuple[ConfusionCounts, float, KappaCI]:
    """Compute pre-label confusion counts, κ, and bootstrap CI for one scorer.

    Returns:
        (pl_counts, pl_kappa, pl_ci).
    """
    pl_counts = pre_label_confusion_counts(scorer_rows)
    pl_kappa_val = pre_label_kappa(scorer_rows)
    pl_ci = pre_label_kappa_interval(
        scorer_rows, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
    )
    return pl_counts, pl_kappa_val, pl_ci


def calibrate_scorer(scorer: str, rows: Sequence[CalibrationLabel]) -> ScorerReport:
    """Compute the full calibration report for one scorer.

    Filters to this scorer's adjudicated rows and computes two confusion matrices:
    headline (scorer_verdict vs human_verdict) and secondary (pre_label vs human_verdict).

    Args:
        scorer: Scorer name (e.g. 'tone_judge').
        rows: All CalibrationLabel rows (multi-scorer OK).
    Returns:
        ScorerReport with headline and secondary κ, CI, precision, recall.
    Raises:
        ValueError: If fewer than 2 adjudicated rows exist for this scorer.
    """
    scorer_rows = [r for r in rows if r.scorer == scorer]
    counts = confusion_counts(scorer_rows)
    kappa_val = cohens_kappa(scorer_rows)
    kci = kappa_interval(scorer_rows, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
    pl_counts, pl_kappa_val, pl_ci = _pre_label_stats(scorer_rows)
    return ScorerReport(
        scorer=scorer,
        counts=counts,
        kappa=kappa_val,
        kappa_lo=kci.lo,
        kappa_hi=kci.hi,
        kappa_n_clusters=kci.n_clusters,
        prec=precision(counts),
        rec=recall(counts),
        pre_label_agreement=agreement_rate(scorer_rows),
        pre_label_counts=pl_counts,
        pre_label_kappa=pl_kappa_val,
        pre_label_kappa_lo=pl_ci.lo,
        pre_label_kappa_hi=pl_ci.hi,
        pre_label_n_clusters=pl_ci.n_clusters,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _kappa_ci_str(lo: float, hi: float, n_clusters: int) -> str:
    """Return the CI display string, substituting a boundary note when lo==hi.

    Args:
        lo: Lower bound of the bootstrap CI.
        hi: Upper bound of the bootstrap CI.
        n_clusters: Number of clusters used in the bootstrap.
    Returns:
        Formatted string for the calibration report.
    """
    if is_boundary_ci(lo, hi):
        note: str = boundary_ci_note(n_clusters)
        return note
    return f"95% CI [{lo:.3f}, {hi:.3f}]"


def _print_scorer_report(report: ScorerReport, print_fn=print) -> None:
    """Print one scorer's two confusion matrices and κ values with bootstrap CIs."""
    c = report.counts
    p = report.pre_label_counts
    print_fn(f"\n{'=' * 62}")
    print_fn(f"Scorer: {report.scorer}  (n={c.n})")
    print_fn(f"{'=' * 62}")
    print_fn("  HEADLINE — scorer_verdict vs human_verdict:")
    print_fn("                       human=T   human=F")
    print_fn(
        f"    scorer=T             {c.tp:6d}    {c.fp:6d}"
        f"  ← FP: dangerous (scorer said pass, human said fail)"
    )
    print_fn(f"    scorer=F             {c.fn:6d}    {c.tn:6d}")
    prec_str = f"{report.prec:.3f}" if report.prec is not None else "undefined"
    rec_str = f"{report.rec:.3f}" if report.rec is not None else "undefined"
    print_fn(f"  Precision : {prec_str}   Recall : {rec_str}")
    headline_ci = _kappa_ci_str(report.kappa_lo, report.kappa_hi, report.kappa_n_clusters)
    print_fn(f"  Headline κ : {report.kappa:.3f}  {headline_ci}  n_rows={c.n}  n_clusters={report.kappa_n_clusters}")
    print_fn("\n  SECONDARY — pre_label vs human_verdict:")
    print_fn("                       human=T   human=F")
    print_fn(
        f"    pre=T                {p.tp:6d}    {p.fp:6d}"
        f"  ← FP: ref-labeller said pass, human said fail"
    )
    print_fn(f"    pre=F                {p.fn:6d}    {p.tn:6d}")
    print_fn(f"  Pre-label agreement : {report.pre_label_agreement:.3f}")
    secondary_ci = _kappa_ci_str(report.pre_label_kappa_lo, report.pre_label_kappa_hi, report.pre_label_n_clusters)
    print_fn(f"  Secondary κ : {report.pre_label_kappa:.3f}  {secondary_ci}  n_rows={p.n}  n_clusters={report.pre_label_n_clusters}")


def run_calibration(
    all_rows: Sequence[CalibrationLabel],
    *,
    print_fn=print,
) -> list[ScorerReport]:
    """Run calibration for every scorer present in all_rows.

    Prints one matrix per scorer — never a single aggregate. Skips scorers
    with fewer than 2 adjudicated rows.

    Args:
        all_rows: CalibrationLabel rows across all scorers.
        print_fn: Output callable (injectable for testing).
    Returns:
        List of ScorerReport, one per scorer with ≥2 adjudicated rows.
    """
    scorers = list(dict.fromkeys(r.scorer for r in all_rows))
    reports: list[ScorerReport] = []
    for scorer in scorers:
        scorer_rows = [r for r in all_rows if r.scorer == scorer]
        adj_count = sum(1 for r in scorer_rows if r.human_verdict is not None)
        if adj_count < 2:
            print_fn(f"\n[SKIP] {scorer}: only {adj_count} adjudicated row(s) — need ≥2")
            continue
        report = calibrate_scorer(scorer, all_rows)
        _print_scorer_report(report, print_fn)
        reports.append(report)
    return reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: print calibration matrices for a labels JSONL file.

    Usage:
        python evals/calibration.py [--file PATH]
        python -m evals calibrate [--file PATH]

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Per-scorer confusion matrices and Cohen's κ with bootstrap CI."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=LABELS_FILE,
        help="Path to labels JSONL (default: evals/calibration/labels_v1.jsonl).",
    )
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"ERROR: Labels file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    rows = read_calibration_labels(args.file)
    adj_count = sum(1 for r in rows if r.human_verdict is not None)
    print(f"Loaded {len(rows)} rows; {adj_count} adjudicated.")
    run_calibration(rows)


if __name__ == "__main__":
    main()
