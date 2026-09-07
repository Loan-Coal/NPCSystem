"""
Module: adjudication_yield
Layer: evals (eval harness — not part of src/)
Purpose: Project what ADJUDICATING the pre-labels already sitting in the labels file
         would yield against DEC-260's adequacy floor, per scorer — so a maintainer
         knows, before a multi-hour keep/flip push, which scorers that push can lift to
         a computable kappa and which it cannot lift at all
         (measurement-remediation Phase 5, DEC-272).
Dependencies: argparse, dataclasses, sys, typing; calibration_records (CalibrationLabel,
         read_calibration_labels, LABELS_FILE), label_adequacy (floor constants + the
         private clean/minority helpers, reused rather than re-derived — the same
         sibling-private-helper precedent label_export_yield.py already sets),
         label_export_strata (case_id_of)
Used by: evals/__main__.py ("adjudication-yield" verb), Makefile adjudication-yield target,
         tests/unit/evals/test_adjudication_yield.py
Does NOT: import from src/npc_engine/, read or write anything but the labels file it is
          pointed at (read-only), or gate anything — this is a report, not a check.
          The gate is scripts/check_label_adequacy.py, which measures the CURRENT state;
          this projects a HYPOTHETICAL one and must never be confused for the former.

Why this exists alongside label_export_yield.py. That module projects the same DEC-260
floor for labels not yet WRITTEN (what a fresh export could produce). This one projects it
for labels written but not yet ADJUDICATED. Those are different populations, and the gap
between them is a real blind spot: a pending pre-label is excluded from an export
projection (its key is already labelled) and contributes nothing to adequacy
(label_adequacy._clean_adjudicated keeps only rows with a human verdict), so before this
module nothing in the harness could answer "what do the pre-labels I already have buy me?"
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from calibration_records import LABELS_FILE, CalibrationLabel, read_calibration_labels
from label_adequacy import MIN_CASE_CLUSTERS, MIN_MINORITY_LABELS, _clean_adjudicated
from label_export_strata import case_id_of


@dataclass(frozen=True)
class AdjudicationYield:
    """What adjudicating one scorer's pending pre-labels would yield against the floor.

    Attributes:
        scorer: Scorer identifier being projected.
        adjudicated_n: Rows already carrying a usable human verdict.
        minority_n: Minority-class count among those — today's adequacy number.
        n_clusters: Case clusters those adjudicated rows span.
        pending_n: Rows with a pre_label and no human verdict — the push's workload.
        pending_pass: Pending rows whose pre_label is True.
        pending_fail: Pending rows whose pre_label is False.
        keep_all_minority_n: Minority count if every pending row were adjudicated
            `keep` — the realistic projection, since keep is the common verdict.
        keep_all_n_clusters: Clusters spanned by adjudicated plus pending rows.
        meets_floor: True iff the keep-all projection clears both DEC-260 floors.
        flips_needed: Minority labels still short under keep-all; 0 when met.
        flips_available: Pending rows on the majority side — the only rows a flip
            could move into the minority class.
        minority_is_fail: Which class is the scarce one under keep-all. True when
            FAIL is the minority (the usual case: scorers mostly agree), False when
            PASS is. Determines which way a flip has to go to help.
        reason: Human-readable explanation naming the numbers; set only when
            meets_floor is False.
    """

    scorer: str
    adjudicated_n: int
    minority_n: int
    n_clusters: int
    pending_n: int
    pending_pass: int
    pending_fail: int
    keep_all_minority_n: int
    keep_all_n_clusters: int
    meets_floor: bool
    flips_needed: int
    flips_available: int
    minority_is_fail: bool = True
    reason: str = ""


def pending_rows(rows: Sequence[CalibrationLabel]) -> list[CalibrationLabel]:
    """Rows a keep/flip adjudication pass could act on.

    A row qualifies when it has no human verdict yet AND still carries a pre_label:
    adjudicate.py hard-refuses `keep`/`flip` on a row whose pre_label was cleared by
    drift, so such a row is not part of this projection's workload.

    Args:
        rows: Any CalibrationLabel rows, one scorer or many.
    Returns:
        The subset that a keep/flip pass can act on, order preserved.
    """
    return [row for row in rows if row.human_verdict is None and row.pre_label is not None]


def _verdict_counts(rows: Sequence[CalibrationLabel]) -> tuple[int, int]:
    """Split adjudicated rows into (pass, fail) counts by human verdict."""
    passes = sum(1 for row in rows if row.human_verdict)
    return passes, len(rows) - passes


def _pre_label_counts(rows: Sequence[CalibrationLabel]) -> tuple[int, int]:
    """Split pending rows into (pass, fail) counts by pre_label."""
    passes = sum(1 for row in rows if row.pre_label)
    return passes, len(rows) - passes


def project_adjudication_yield(scorer: str, rows: Sequence[CalibrationLabel]) -> AdjudicationYield:
    """Project one scorer's keep-all adjudication outcome against DEC-260's floor.

    Args:
        scorer: Scorer identifier to project.
        rows: Every CalibrationLabel row, any scorer — filtered to `scorer` internally.
    Returns:
        The projection, including what a flip-heavy pass could and could not reach.
    """
    scorer_rows = [row for row in rows if row.scorer == scorer]
    clean = _clean_adjudicated(scorer_rows)
    pending = pending_rows(scorer_rows)

    adj_pass, adj_fail = _verdict_counts(clean)
    pend_pass, pend_fail = _pre_label_counts(pending)
    clusters = {case_id_of(row.record_id) for row in clean} | {case_id_of(row.record_id) for row in pending}

    return _build_yield(
        scorer=scorer,
        clean_n=len(clean),
        minority_n=min(adj_pass, adj_fail),
        n_clusters=len({case_id_of(row.record_id) for row in clean}),
        pending=(len(pending), pend_pass, pend_fail),
        keep_all=(adj_pass + pend_pass, adj_fail + pend_fail),
        keep_all_clusters=len(clusters),
    )


def _build_yield(
    *,
    scorer: str,
    clean_n: int,
    minority_n: int,
    n_clusters: int,
    pending: tuple[int, int, int],
    keep_all: tuple[int, int],
    keep_all_clusters: int,
) -> AdjudicationYield:
    """Assemble the AdjudicationYield from the counts project_adjudication_yield derives.

    Split out purely to keep that function under the 40-line cap.
    """
    pending_n, pend_pass, pend_fail = pending
    keep_pass, keep_fail = keep_all
    keep_minority = min(keep_pass, keep_fail)
    meets = keep_minority >= MIN_MINORITY_LABELS and keep_all_clusters >= MIN_CASE_CLUSTERS

    flips_needed = 0 if meets else max(0, MIN_MINORITY_LABELS - keep_minority)
    # Only a pending row on the MAJORITY side can be flipped into the minority class.
    minority_is_fail = keep_fail <= keep_pass
    flips_available = pend_pass if minority_is_fail else pend_fail

    projection = AdjudicationYield(
        scorer=scorer,
        adjudicated_n=clean_n,
        minority_n=minority_n,
        n_clusters=n_clusters,
        pending_n=pending_n,
        pending_pass=pend_pass,
        pending_fail=pend_fail,
        keep_all_minority_n=keep_minority,
        keep_all_n_clusters=keep_all_clusters,
        meets_floor=meets,
        flips_needed=flips_needed,
        flips_available=flips_available,
        minority_is_fail=minority_is_fail,
    )
    return projection if meets else replace(projection, reason=_reason(projection))


def _reason_head(y: AdjudicationYield) -> str:
    """The shared opening clause naming the projected numbers and the floor."""
    return (
        f"{y.scorer}: adjudicating every pending row as `keep` yields "
        f"{y.keep_all_minority_n} minority item(s) across {y.keep_all_n_clusters} cluster(s) "
        f"(need >={MIN_MINORITY_LABELS} across >={MIN_CASE_CLUSTERS})"
    )


def _reason(y: AdjudicationYield) -> str:
    """Explain why the keep-all projection misses the floor, and whether flips can close it."""
    side = "FAIL" if y.minority_is_fail else "PASS"
    head = _reason_head(y)
    if y.keep_all_n_clusters < MIN_CASE_CLUSTERS:
        return f"{head}; the cluster arm alone is short, so new cases are required"
    if y.pending_n == 0:
        return (
            f"{head}; there are no pending pre-labels for this scorer, so adjudication cannot "
            "move it at all — a fresh labelling pass is required"
        )
    if y.flips_available == 0:
        return (
            f"{head}; every one of its {y.pending_n} pending pre-label(s) is already {side}, "
            "so there is nothing left to flip into the minority class"
        )
    if y.flips_needed > y.flips_available:
        return (
            f"{head}; closing it needs {y.flips_needed} flip(s) to {side} but only "
            f"{y.flips_available} pending row(s) can be flipped — not reachable by adjudication alone"
        )
    pending_on_minority_side = y.pending_fail if y.minority_is_fail else y.pending_pass
    zero_note = (
        f", and the pre-labeller returned zero {side} among them" if pending_on_minority_side == 0 else ""
    )
    return (
        f"{head}; reachable only if the adjudicator flips >={y.flips_needed} of the "
        f"{y.flips_available} pending row(s) to {side}{zero_note}"
    )


def project_all(
    rows: Sequence[CalibrationLabel], scorers: Sequence[str] | None = None
) -> list[AdjudicationYield]:
    """Project every scorer present in the labels, in the order calibration iterates them.

    Args:
        rows: Every CalibrationLabel row.
        scorers: Explicit scorer order; defaults to the distinct scorers found in
            `rows`, which is exactly how calibration.run_calibration derives its own
            population — so this report never covers a different set than the one
            `python -m evals calibrate` will iterate.
    Returns:
        One AdjudicationYield per scorer.
    """
    names = list(scorers) if scorers is not None else list(dict.fromkeys(row.scorer for row in rows))
    return [project_adjudication_yield(scorer, rows) for scorer in names]


def format_yield_table(yields: Sequence[AdjudicationYield]) -> str:
    """Render a per-scorer adjudication-yield report, floor numbers included.

    Args:
        yields: Projections in the order they should print.
    Returns:
        A multi-line report, one row per scorer plus a header naming the floor.
    """
    lines = [
        f"Adequacy floor: >={MIN_MINORITY_LABELS} minority labels across >={MIN_CASE_CLUSTERS} clusters.",
        "Projection assumes every pending pre-label is adjudicated `keep`.",
    ]
    for y in yields:
        verdict = "CLEARS FLOOR" if y.meets_floor else "SHORT"
        lines.append(
            f"  {y.scorer:<28} now {y.minority_n}/{y.n_clusters}c "
            f"+ pending {y.pending_n} ({y.pending_pass}P/{y.pending_fail}F) "
            f"= keep-all {y.keep_all_minority_n}/{y.keep_all_n_clusters}c  [{verdict}]"
        )
        if y.reason:
            lines.append(f"    {y.reason}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    """Build the `adjudication-yield` verb's argument parser."""
    parser = argparse.ArgumentParser(
        description="Project what adjudicating the pending pre-labels would yield (DEC-272)."
    )
    parser.add_argument("--file", type=Path, default=LABELS_FILE, help="Labels file to project over.")
    parser.add_argument(
        "--scorer", action="append", default=None,
        help="Restrict to one scorer; repeatable. Default: every scorer in the file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Print the per-scorer adjudication-yield projection. Always exits 0 — this is a report."""
    args = _build_parser().parse_args(argv)
    if not args.file.exists():
        print(f"labels file not found: {args.file}", file=sys.stderr)
        return 1

    rows = read_calibration_labels(args.file)
    yields = project_all(rows, args.scorer)
    print(f"Loaded {len(rows)} row(s) from {args.file}.")
    print(format_yield_table(yields))
    return 0


if __name__ == "__main__":
    sys.exit(main())
