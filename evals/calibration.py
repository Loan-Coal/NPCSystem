"""
Module: calibration
Layer: evals (eval harness — not part of src/)
Purpose: Per-scorer calibration reports with two confusion matrices each: a headline
         (scorer_verdict vs human_verdict) and a secondary (pre_label vs human_verdict),
         each with Cohen's κ, a seeded cluster-bootstrap CI, and a Holm-Bonferroni
         companion interval. Prints one pair of matrices per scorer — never a single
         aggregate. Called by `make eval-calibrate`.
Dependencies: calibration_records, dataclasses, logging, math, random, pathlib, sys, typing
Used by: make eval-calibrate (CLI), tests/unit/evals/test_calibration.py

NOTE: This file exceeds the 300-line limit (DEC-169). Split would be artificial because
      all functions form a single coherent calibration pipeline and are tightly coupled
      via shared data types (KappaCI, ScorerReport). Future work: extract bootstrap
      internals into evals/bootstrap.py if the file grows further.
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
CI_NOMINAL_ALPHA: float = 0.05
CI_LO_PERCENTILE: float = 0.025
CI_HI_PERCENTILE: float = 0.975
INTERVALS_PER_SCORER: int = 2  # headline κ CI + secondary κ CI per scorer in a run

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class KappaCI(NamedTuple):
    """Bootstrap confidence interval for Cohen's κ with cluster metadata.

    Attributes:
        lo: 2.5th-percentile bootstrap κ (nominal 95% CI lower bound).
        hi: 97.5th-percentile bootstrap κ (nominal 95% CI upper bound).
        n_clusters: Number of unique case clusters in the resampled population.
        n_rows: Total adjudicated rows (= sum of cluster sizes).
        holm_lo: Holm-Bonferroni adjusted lower bound (α*=α/family_size); None when family_size=1.
        holm_hi: Holm-Bonferroni adjusted upper bound; None when family_size=1.
        holm_family_size: Number of simultaneous intervals in the calibration family; None when no adjustment.
    """

    lo: float
    hi: float
    n_clusters: int
    n_rows: int
    holm_lo: float | None = None
    holm_hi: float | None = None
    holm_family_size: int | None = None


@dataclass(frozen=True)
class ConfusionCounts:
    """TP/FP/FN/TN for one scorer against human verdicts.

    FP is the dangerous cell: the scorer said "pass" but the human said "fail".

    Attributes:
        n_excluded_drifted: Adjudicated rows left out of this matrix because
            needs_review is set — the content changed under the stored human
            verdict, so scoring it here would judge the machine's new output
            against the human's old verdict (EVAL-P19.0).
        n_excluded_pre_label_cleared: SECONDARY axis only — clean adjudicated
            rows further excluded because pre_label is None (label_merge
            cleared it on drift, EVAL-P20.3a / ISSUE-153). Always 0 on the
            headline (scorer_verdict) matrix.
    """

    tp: int
    fp: int
    fn: int
    tn: int
    n_excluded_drifted: int = 0
    n_excluded_pre_label_cleared: int = 0

    @property
    def n(self) -> int:
        """Total adjudicated rows included in the matrix (excludes drifted)."""
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
    kappa_holm_lo: float | None = None
    kappa_holm_hi: float | None = None
    pre_label_kappa_holm_lo: float | None = None
    pre_label_kappa_holm_hi: float | None = None
    holm_family_size: int | None = None


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


def _adjudicated_rows(
    rows: Sequence[CalibrationLabel],
) -> tuple[list[CalibrationLabel], int]:
    """Split rows into (clean adjudicated rows, count excluded as drifted).

    A drifted row (needs_review=True) carries a human verdict recorded
    against text the scorer no longer produces — label_merge flags it rather
    than silently re-pointing the verdict at new content. Every calibration
    statistic must exclude it, on both the headline and secondary axis, or
    the human's old judgement gets scored against the machine's new output.

    Args:
        rows: CalibrationLabel rows (any adjudication state).
    Returns:
        (clean, n_excluded_drifted) — clean rows have human_verdict set and
        needs_review False; n_excluded_drifted counts adjudicated rows left
        out because needs_review was True.
    """
    adjudicated = [r for r in rows if r.human_verdict is not None]
    clean = [r for r in adjudicated if not r.needs_review]
    return clean, len(adjudicated) - len(clean)


def _secondary_axis_rows(
    rows: Sequence[CalibrationLabel],
) -> tuple[list[CalibrationLabel], int, int]:
    """Clean adjudicated rows with a valid pre_label — SECONDARY axis population.

    Applies the same needs_review exclusion as _adjudicated_rows, then further
    excludes rows whose pre_label is None — label_merge clears pre_label to
    None on content drift (EVAL-P20.3a / ISSUE-153) because the reference-
    labeller opinion attached to the old content is not valid for the new
    content. A cleared pre_label means "no current opinion", not "opinion:
    False" — silently tallying it as False would misrepresent the reference
    labeller's agreement rate.

    Args:
        rows: CalibrationLabel rows (any adjudication state).
    Returns:
        (clean, n_excluded_drifted, n_excluded_pre_label_cleared).
    """
    clean, n_excluded_drifted = _adjudicated_rows(rows)
    with_pre_label = [r for r in clean if r.pre_label is not None]
    n_excluded_pre_label_cleared = len(clean) - len(with_pre_label)
    return with_pre_label, n_excluded_drifted, n_excluded_pre_label_cleared


def confusion_counts(rows: Sequence[CalibrationLabel]) -> ConfusionCounts:
    """Tally TP/FP/FN/TN — HEADLINE axis: scorer_verdict vs human_verdict.

    FP = scorer_verdict=True, human_verdict=False — the dangerous cell
    (scorer said pass, human said fail).

    Args:
        rows: CalibrationLabel rows (unadjudicated and drifted rows are skipped).
    Returns:
        ConfusionCounts from clean adjudicated rows, with n_excluded_drifted set.
    """
    adj, n_excluded_drifted = _adjudicated_rows(rows)
    tp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.scorer_verdict is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.scorer_verdict is False and r.human_verdict is False)
    return ConfusionCounts(tp=tp, fp=fp, fn=fn, tn=tn, n_excluded_drifted=n_excluded_drifted)


def pre_label_confusion_counts(rows: Sequence[CalibrationLabel]) -> ConfusionCounts:
    """Tally TP/FP/FN/TN — SECONDARY axis: pre_label vs human_verdict.

    FP = pre_label=True, human_verdict=False (reference labeller said pass,
    human said fail).

    Args:
        rows: CalibrationLabel rows (unadjudicated, drifted, and pre_label=None
            rows are skipped — see _secondary_axis_rows).
    Returns:
        ConfusionCounts from clean rows with a real pre_label, with both
        n_excluded_drifted and n_excluded_pre_label_cleared set.
    """
    adj, n_excluded_drifted, n_excluded_pre_label_cleared = _secondary_axis_rows(rows)
    tp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is True)
    fp = sum(1 for r in adj if r.pre_label is True and r.human_verdict is False)
    fn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is True)
    tn = sum(1 for r in adj if r.pre_label is False and r.human_verdict is False)
    return ConfusionCounts(
        tp=tp, fp=fp, fn=fn, tn=tn,
        n_excluded_drifted=n_excluded_drifted,
        n_excluded_pre_label_cleared=n_excluded_pre_label_cleared,
    )


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
        ValueError: If fewer than 2 clean adjudicated rows are available
            (drifted rows do not count — see _adjudicated_rows).
    """
    adj, _ = _adjudicated_rows(rows)
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
        ValueError: If fewer than 2 rows with a real pre_label are available
            (drifted rows, and rows whose pre_label was cleared to None on
            drift, do not count — see _secondary_axis_rows).
    """
    adj, _, _ = _secondary_axis_rows(rows)
    if len(adj) < 2:
        raise ValueError(f"pre_label_kappa requires ≥2 rows with a pre_label; got {len(adj)}")
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


def _holm_percentile_bounds(kappas: list[float], family_size: int) -> tuple[float, float]:
    """Return (holm_lo, holm_hi) from a sorted bootstrap distribution at α*=α/family_size."""
    total = len(kappas)
    alpha_adj = CI_NOMINAL_ALPHA / family_size
    holm_lo_idx = math.floor(total * (alpha_adj / 2.0))
    holm_hi_raw = math.ceil(total * (1.0 - alpha_adj / 2.0)) - 1
    holm_hi_idx = max(min(holm_hi_raw, total - 1), holm_lo_idx)
    return kappas[holm_lo_idx], kappas[holm_hi_idx]


def _bootstrap_percentile_ci(
    clusters: list[list[CalibrationLabel]],
    kappa_fn: Callable[[list[CalibrationLabel]], float],
    resamples: int,
    seed: int,
    caller: str,
    *,
    family_size: int = 1,
) -> tuple[float, float, float | None, float | None, int, int]:
    """Seeded cluster bootstrap CI; returns (lo, hi, holm_lo, holm_hi, n_clusters, n_rows).

    holm_lo/holm_hi use α*=α/family_size (Holm-Bonferroni); None when family_size=1.

    Args:
        clusters, kappa_fn, resamples, seed, caller: bootstrap parameters.
        family_size: Simultaneous-interval family size for Holm adjustment.
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
    holm_lo: float | None = None
    holm_hi: float | None = None
    if family_size > 1:
        holm_lo, holm_hi = _holm_percentile_bounds(kappas, family_size)
    return kappas[lo_idx], kappas[hi_idx], holm_lo, holm_hi, n_clusters, n_rows


def kappa_interval(
    rows: Sequence[CalibrationLabel],
    resamples: int,
    seed: int,
    *,
    family_size: int = 1,
) -> KappaCI:
    """Bootstrap 95% CI on κ — HEADLINE axis (scorer_verdict vs human_verdict).

    Resamples by **case cluster** (all rows sharing the same case_id prefix move
    together), correcting for intra-case correlation from repeated generations.
    Same rows + seed always produce the same bounds.

    When family_size > 1, also computes Holm-Bonferroni companion bounds at α*=α/family_size
    from the same bootstrap draw (no extra sampling cost).

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are ignored).
        resamples: Number of bootstrap resamples.
        seed: RNG seed — fix it to keep the interval reproducible.
        family_size: Number of simultaneous intervals in the calibration family.
    Returns:
        KappaCI with lo, hi (95% bootstrap CI), n_clusters, n_rows, and optional Holm fields.
    Raises:
        ValueError: If fewer than 2 clean adjudicated rows (drifted rows
            excluded — see _adjudicated_rows) or all bootstrap samples degenerate.
    """
    adj, _ = _adjudicated_rows(rows)
    if len(adj) < 2:
        raise ValueError(f"kappa_interval requires ≥2 adjudicated rows; got {len(adj)}")
    clusters = _extract_case_clusters(adj)
    lo, hi, holm_lo, holm_hi, n_clusters, n_rows = _bootstrap_percentile_ci(
        clusters, cohens_kappa, resamples, seed, "kappa_interval", family_size=family_size
    )
    return KappaCI(
        lo=lo, hi=hi, n_clusters=n_clusters, n_rows=n_rows,
        holm_lo=holm_lo, holm_hi=holm_hi,
        holm_family_size=family_size if family_size > 1 else None,
    )


def pre_label_kappa_interval(
    rows: Sequence[CalibrationLabel],
    resamples: int,
    seed: int,
    *,
    family_size: int = 1,
) -> KappaCI:
    """Bootstrap 95% CI on κ — SECONDARY axis (pre_label vs human_verdict).

    Resamples by **case cluster** (same case-level correction as kappa_interval).
    When family_size > 1, also computes Holm-Bonferroni companion bounds.

    Args:
        rows: CalibrationLabel rows (unadjudicated rows are ignored).
        resamples: Number of bootstrap resamples.
        seed: RNG seed — fix it to keep the interval reproducible.
        family_size: Number of simultaneous intervals in the calibration family.
    Returns:
        KappaCI with lo, hi (95% bootstrap CI), n_clusters, n_rows, and optional Holm fields.
    Raises:
        ValueError: If fewer than 2 rows with a real pre_label (drifted rows,
            and rows whose pre_label was cleared to None on drift, excluded —
            see _secondary_axis_rows) or all bootstrap samples degenerate.
    """
    adj, _, _ = _secondary_axis_rows(rows)
    if len(adj) < 2:
        raise ValueError(
            f"pre_label_kappa_interval requires ≥2 rows with a pre_label; got {len(adj)}"
        )
    clusters = _extract_case_clusters(adj)
    lo, hi, holm_lo, holm_hi, n_clusters, n_rows = _bootstrap_percentile_ci(
        clusters, pre_label_kappa, resamples, seed, "pre_label_kappa_interval",
        family_size=family_size,
    )
    return KappaCI(
        lo=lo, hi=hi, n_clusters=n_clusters, n_rows=n_rows,
        holm_lo=holm_lo, holm_hi=holm_hi,
        holm_family_size=family_size if family_size > 1 else None,
    )


def agreement_rate(rows: Sequence[CalibrationLabel]) -> float:
    """Fraction of adjudicated rows (with a real pre_label) where pre_label == human_verdict.

    This is the free pre-label-vs-human agreement metric (DEC-153 §7). Rows
    whose pre_label was cleared to None on drift (ISSUE-153) are excluded —
    otherwise `None == human_verdict` is always False and silently counts as
    disagreement rather than "no opinion to compare".

    Args:
        rows: CalibrationLabel rows.
    Returns:
        Agreement fraction in [0, 1].
    Raises:
        ValueError: If no adjudicated rows with a real pre_label exist.
    """
    adj = [r for r in rows if r.human_verdict is not None and r.pre_label is not None]
    if not adj:
        raise ValueError("agreement_rate requires at least 1 adjudicated row with a pre_label")
    agree = sum(1 for r in adj if r.pre_label == r.human_verdict)
    return agree / len(adj)


# ---------------------------------------------------------------------------
# Per-scorer report
# ---------------------------------------------------------------------------


def _pre_label_stats(
    scorer_rows: Sequence[CalibrationLabel],
    *,
    family_size: int = 1,
) -> tuple[ConfusionCounts, float, KappaCI]:
    """Compute pre-label confusion counts, κ, and bootstrap CI for one scorer.

    Args:
        scorer_rows: CalibrationLabel rows for a single scorer.
        family_size: Passed to pre_label_kappa_interval for Holm adjustment.
    Returns:
        (pl_counts, pl_kappa, pl_ci).
    """
    pl_counts = pre_label_confusion_counts(scorer_rows)
    pl_kappa_val = pre_label_kappa(scorer_rows)
    pl_ci = pre_label_kappa_interval(
        scorer_rows, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
        family_size=family_size,
    )
    return pl_counts, pl_kappa_val, pl_ci


def calibrate_scorer(
    scorer: str,
    rows: Sequence[CalibrationLabel],
    *,
    family_size: int = 1,
) -> ScorerReport:
    """Full calibration report for one scorer: headline + secondary matrices, κ, and Holm CIs.

    Args:
        scorer, rows, family_size: scorer name, all rows (multi-scorer OK), Holm family size.
    Returns:
        ScorerReport, or raises ValueError if fewer than 2 adjudicated rows.
    """
    scorer_rows = [r for r in rows if r.scorer == scorer]
    counts = confusion_counts(scorer_rows)
    kappa_val = cohens_kappa(scorer_rows)
    kci = kappa_interval(scorer_rows, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED,
                         family_size=family_size)
    pl_counts, pl_kappa_val, pl_ci = _pre_label_stats(scorer_rows, family_size=family_size)
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
        kappa_holm_lo=kci.holm_lo,
        kappa_holm_hi=kci.holm_hi,
        pre_label_kappa_holm_lo=pl_ci.holm_lo,
        pre_label_kappa_holm_hi=pl_ci.holm_hi,
        holm_family_size=family_size if family_size > 1 else None,
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


def _print_headline_matrix(report: ScorerReport, print_fn) -> None:
    """Print the HEADLINE confusion matrix (scorer_verdict vs human_verdict)."""
    c = report.counts
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
    if report.holm_family_size is not None and report.kappa_holm_lo is not None:
        alpha_adj = CI_NOMINAL_ALPHA / report.holm_family_size
        print_fn(f"  Headline κ Holm-adj [{report.kappa_holm_lo:.3f}, {report.kappa_holm_hi:.3f}]"
                 f"  (family={report.holm_family_size}, α*={alpha_adj:.4f})")


def _print_secondary_matrix(report: ScorerReport, print_fn) -> None:
    """Print the SECONDARY confusion matrix (pre_label vs human_verdict)."""
    p = report.pre_label_counts
    if p.n_excluded_pre_label_cleared:
        print_fn(
            f"  ⚠ {p.n_excluded_pre_label_cleared} row(s) additionally excluded from this axis: "
            f"pre_label cleared to None on drift (see label_merge)"
        )
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
    if report.holm_family_size is not None and report.pre_label_kappa_holm_lo is not None:
        alpha_adj = CI_NOMINAL_ALPHA / report.holm_family_size
        print_fn(f"  Secondary κ Holm-adj [{report.pre_label_kappa_holm_lo:.3f}, {report.pre_label_kappa_holm_hi:.3f}]"
                 f"  (family={report.holm_family_size}, α*={alpha_adj:.4f})")


def _print_scorer_report(report: ScorerReport, print_fn=print) -> None:
    """Print one scorer's two confusion matrices and κ values with bootstrap CIs."""
    print_fn(f"\n{'=' * 62}")
    print_fn(f"Scorer: {report.scorer}  (n={report.counts.n})")
    print_fn(f"{'=' * 62}")
    if report.counts.n_excluded_drifted:
        print_fn(
            f"  ⚠ {report.counts.n_excluded_drifted} row(s) excluded: needs_review is "
            f"set — content drifted since adjudication (see label_merge)"
        )
    _print_headline_matrix(report, print_fn)
    _print_secondary_matrix(report, print_fn)


def _print_family_disclosure(eligible_count: int, family_size: int, print_fn) -> None:
    """Print the family-wise error rate disclosure header to print_fn."""
    fwer = 1.0 - (1.0 - CI_NOMINAL_ALPHA) ** family_size if family_size > 0 else 0.0
    print_fn(f"\nFamily-wise disclosure: {family_size} simultaneous intervals "
             f"({eligible_count} scorer(s) × {INTERVALS_PER_SCORER} axes).")
    if family_size > 1:
        alpha_adj = CI_NOMINAL_ALPHA / family_size
        print_fn(f"  Nominal: 95% per-interval CI (α={CI_NOMINAL_ALPHA:.3f}). "
                 f"FWER: 1−0.95^{family_size} = {fwer:.3f}.")
        print_fn(f"  Holm α*={alpha_adj:.4f} → each companion CI at "
                 f"{(1.0 - alpha_adj) * 100:.2f}%. Quote these for multi-scorer claims.")


def run_calibration(
    all_rows: Sequence[CalibrationLabel],
    *,
    print_fn=print,
) -> list[ScorerReport]:
    """Calibrate every scorer in all_rows; print family disclosure + one matrix per scorer.

    Args:
        all_rows: CalibrationLabel rows across all scorers.
        print_fn: Output callable (injectable for testing).
    Returns:
        List of ScorerReport, one per scorer with ≥2 adjudicated rows.
    """
    scorers = list(dict.fromkeys(r.scorer for r in all_rows))
    eligible = [
        s for s in scorers
        if sum(1 for r in all_rows if r.scorer == s and r.human_verdict is not None) >= 2
    ]
    family_size = INTERVALS_PER_SCORER * len(eligible)
    _print_family_disclosure(len(eligible), family_size, print_fn)
    reports: list[ScorerReport] = []
    for scorer in scorers:
        scorer_rows = [r for r in all_rows if r.scorer == scorer]
        adj_count = sum(1 for r in scorer_rows if r.human_verdict is not None)
        if adj_count < 2:
            print_fn(f"\n[SKIP] {scorer}: only {adj_count} adjudicated row(s) — need ≥2")
            continue
        report = calibrate_scorer(scorer, all_rows, family_size=family_size)
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
