"""
Module: label_export_stratified
Layer: evals (eval harness — not part of src/)
Purpose: CLI verb wrapping label_export around DEC-260's adequacy floor: for
         each in-scope judge, project the best-case minority-label ceiling
         BEFORE any batch is written (label_export_yield), print the
         projection table, and write a stratified batch — oversampling every
         available expected-negative candidate (label_export_sampling) — only
         for judges whose ceiling clears the floor. A judge whose ceiling
         cannot clear the floor is reported with its numbers and gets no
         batch: nothing is exported that cannot support a kappa estimate
         (this task, 2026-09-04).
Dependencies: argparse, json, pathlib, sys; calibration_records, eval_records,
         export_item, label_export (write_export_batches), label_export_sampling,
         label_export_strata, label_export_yield, label_survival
Used by: python -m evals label-export-stratified; make label-export-stratified
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from calibration_records import LABELS_FILE, read_calibration_labels
from eval_records import read_transcript
from export_item import ExportItem, build_export_items
from label_export import write_export_batches
from label_export_sampling import select_stratified_batch
from label_export_strata import CASE_STRATA_FILE, load_expected_negative_cases
from label_export_yield import ProjectedYield, format_projection_table, project_all
from label_survival import simulate_survival

# Judges this exporter oversamples for — the 3 surviving calibrated scorers after
# measurement-remediation Phase 2 (DEC-269). refusal_judge is retired (its axis
# folded into affirms_judge, ISSUE-276 closed) rather than merely excluded, and
# liveness_judge (formerly the tone_judge-labelled guard liveness check, Phase 2b)
# is deliberately absent too: a precondition-shaped check, not a calibration target,
# same reasoning as schema/min_length. Neither ever had case_neg/case_adv coverage
# to oversample from anyway — the candidate transcript this tool targets carries no
# refusal_judge records at all, and liveness_judge is structurally near-constant.
IN_SCOPE_SCORERS: tuple[str, ...] = ("commits_judge", "tone_judge", "affirms_judge")

# Fixed and logged so the same transcript + labels always yield the same batch
# (DEC-176 seed-work convention: every RNG seed the harness uses is pinned and
# printed, never left to draw from system entropy).
DEFAULT_SEED: int = 20260904

# Stdout/stderr are already reconfigured to UTF-8 by evals.__main__ at import
# time for every verb dispatched through `python -m evals ...` — this module
# does not duplicate that (see __main__.py's _force_utf8_streams docstring).


def _load_vocabulary(path: Path | None) -> dict[str, Any] | None:
    """Load an optional vocabulary snapshot, mirroring label_export's own loader."""
    if path is not None and path.exists():
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    return None


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the label-export-stratified verb."""
    parser = argparse.ArgumentParser(
        prog="python -m evals label-export-stratified",
        description=(
            "Stratified label-export: report each in-scope judge's projected "
            "best-case minority-label ceiling against DEC-260's adequacy floor, "
            "then write an oversampled batch only for judges that clear it."
        ),
    )
    parser.add_argument("--transcript", type=Path, required=True, metavar="PATH")
    parser.add_argument("--out-dir", type=Path, required=True, metavar="DIR")
    parser.add_argument("--labels", type=Path, default=LABELS_FILE, metavar="PATH")
    parser.add_argument("--strata", type=Path, default=CASE_STRATA_FILE, metavar="PATH")
    parser.add_argument("--vocabulary", type=Path, default=None, metavar="PATH")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, metavar="N")
    parser.add_argument(
        "--scorer",
        action="append",
        default=None,
        metavar="NAME",
        help=f"Judge to project/export; repeatable. Default: {', '.join(IN_SCOPE_SCORERS)}.",
    )
    return parser


def _export_cleared_batches(
    projections: Sequence[ProjectedYield],
    candidate_items: Sequence[ExportItem],
    already_labelled: frozenset[tuple[str, str]],
    negative_cases: frozenset[str],
    *,
    seed: int,
    out_dir: Path,
) -> int:
    """Write a stratified batch for every projection that clears the floor.

    Args:
        projections: One ProjectedYield per requested judge.
        candidate_items: Every ExportItem built from the candidate transcript.
        already_labelled: (record_id, scorer) keys that already carry a label.
        negative_cases: Declared expected-negative case_ids.
        seed: RNG seed for select_stratified_batch.
        out_dir: Parent directory; each judge's batch goes in its own subdirectory.
    Returns:
        Count of projections that did NOT clear the floor (no batch written for them).
    """
    refused = 0
    for projection in projections:
        if not projection.meets_floor:
            refused += 1
            continue
        batch_items = select_stratified_batch(
            projection.scorer, candidate_items, already_labelled, negative_cases, seed=seed
        )
        judge_out_dir = out_dir / projection.scorer
        paths = write_export_batches(batch_items, judge_out_dir)
        print(
            f"{projection.scorer}: wrote {len(batch_items)} item(s) across {len(paths)} batch file(s) -> {judge_out_dir}",
            file=sys.stderr,
        )
    return refused


def main(argv: Sequence[str] | None = None) -> int:
    """Print the projected-yield report, then export a batch per judge that clears it.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 if every requested judge cleared the floor and got a batch; 1 if any
        judge was refused (its numbers are still printed; no batch is written
        for it, and the judges that did clear the floor still get theirs).
    """
    args = _build_parser().parse_args(argv)

    labels = read_calibration_labels(args.labels)
    survival = simulate_survival(labels, args.transcript)
    negative_cases = load_expected_negative_cases(args.strata)

    transcript = read_transcript(args.transcript)
    candidate_items = build_export_items(list(transcript.records), _load_vocabulary(args.vocabulary))

    scorers = tuple(args.scorer) if args.scorer else IN_SCOPE_SCORERS
    projections = project_all(scorers, labels, frozenset(survival.survives), candidate_items, negative_cases)

    print(f"seed: {args.seed}  transcript: {args.transcript}", file=sys.stderr)
    print(format_projection_table(projections), file=sys.stderr)

    already_labelled = frozenset(row.key for row in labels)
    refused = _export_cleared_batches(
        projections, candidate_items, already_labelled, negative_cases, seed=args.seed, out_dir=args.out_dir
    )

    if refused:
        print(
            f"{refused} of {len(projections)} judge(s) refused — no batch written for them (see table above).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
