"""
Module: oracle_labeller
Layer: scripts (dev tooling — not part of src/ or the evals package)
Purpose: Emit calibration labels by a DECLARED RULE with a KNOWN-BY-CONSTRUCTION
         confusion matrix, so the export → import → adjudicate → calibrate chain
         can be checked against a kappa computed by hand. scripts/mock_labeller.py
         emits *random* labels: it proves data of the right shape moves, and can
         never prove the pipeline computes the right value. This module can.
         The data model, the named errors and the rule itself live in
         oracle_matrix.py (300-line cap); this module owns reading the artifact
         and the CLI, and re-exports the rest for callers and tests.
Dependencies: argparse, json, pathlib, sys, oracle_matrix, record_identity (evals/)
Used by: make mock-calibrate-oracle (EVAL-P15.1)
Does NOT: call any LLM, and never writes to calibration_records.LABELS_FILE.

THE DECLARED RULE
-----------------
Rows for the target scorer are partitioned by their real `scorer_verdict` (read
from the judged file, which is why this is an *oracle* and not a labeller), and
each partition is sorted by item id. Then:

    scorer_verdict=True  partition: first  tp rows -> pre_label=True
                                    next   fp rows -> pre_label=False
    scorer_verdict=False partition: first  fn rows -> pre_label=True
                                    next   tn rows -> pre_label=False

Every remaining row is omitted. `scripts/oracle_adjudicate.py` then copies
pre_label into human_verdict verbatim, so the HEADLINE axis
(scorer_verdict × human_verdict) is exactly the requested (tp, fp, fn, tn) and
its kappa is predictable in closed form.

⚠️ These labels are synthetic. The `--model` identifier is 'oracle-matrix-v1' and
every note is prefixed ORACLE:, so oracle rows are greppable and can never be
mistaken for human verdicts. `evals/synthetic_label_guard.py` refuses any
label-import run carrying that prefix at the real labels file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from oracle_matrix import (
    MatrixCaps,
    OracleOutputPathError,
    RequestedMatrix,
    UnsatisfiableMatrixError,
    assign_labels,
    partition_by_verdict,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from record_identity import composite_item_id  # noqa: E402

# Re-exported so callers and tests have one import site for the oracle.
__all__ = [
    "MatrixCaps",
    "OracleOutputPathError",
    "RequestedMatrix",
    "UnsatisfiableMatrixError",
    "ORACLE_BATCH_DIR",
    "ORACLE_LABELS_FILE",
    "ORACLE_MODEL_ID",
    "ORACLE_RAW_FILE",
    "assign_labels",
    "check_out_path",
    "matrix_caps",
    "oracle_rows",
    "partition_by_verdict",
    "read_batch_items",
    "read_verdicts",
    "main",
]

# ---------------------------------------------------------------------------
# Constants — the mandatory paths from EVAL-P15.1
# ---------------------------------------------------------------------------

ORACLE_MODEL_ID: str = "oracle-matrix-v1"

_REPO_ROOT: Path = Path(__file__).resolve().parents[1]

ORACLE_BATCH_DIR: Path = _REPO_ROOT / "evals" / "calibration" / "oracle_batches"
ORACLE_LABELS_FILE: Path = _REPO_ROOT / "evals" / "calibration" / "oracle" / "labels_oracle.jsonl"
ORACLE_RAW_FILE: Path = _REPO_ROOT / "evals" / "calibration" / "oracle" / "raw_labels_oracle.jsonl"

# Never write here. Checked by name so this module needs no import from
# evals/calibration*, which would couple the oracle to the code it validates.
_REAL_LABELS_FILENAME: str = "labels_v1.jsonl"


# ---------------------------------------------------------------------------
# Reading the artifact
# ---------------------------------------------------------------------------


def read_batch_items(batch_dir: Path) -> list[dict[str, Any]]:
    """Read every item from every batch_*.json in a label-export directory.

    Args:
        batch_dir: Directory holding batch_*.json files from label-export.
    Returns:
        Items in batch-file order.
    Raises:
        FileNotFoundError: If no batch files are found — a silent empty run
            would look like a completed pass with nothing labelled.
    """
    paths = sorted(batch_dir.glob("batch_*.json"))
    if not paths:
        raise FileNotFoundError(f"No batch_*.json files found in {batch_dir}")

    items: list[dict[str, Any]] = []
    for path in paths:
        items.extend(json.loads(path.read_text(encoding="utf-8")))
    return items


def read_verdicts(judged_paths: Sequence[Path]) -> dict[str, bool]:
    """Build an item_id→scorer_verdict index from judged JSONL file(s).

    Args:
        judged_paths: judged.jsonl and/or deterministic_judged.jsonl paths.
    Returns:
        Dict mapping composite item_id to the recorded `passed` bool.
    Raises:
        FileNotFoundError: If any path does not exist.
    """
    index: dict[str, bool] = {}
    for path in judged_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            key = composite_item_id(obj["record_id"], int(obj.get("repetition", 0)))
            index[key] = bool(obj.get("passed", False))
    return index


def matrix_caps(batch_dir: Path, judged_paths: Sequence[Path], scorer: str) -> MatrixCaps:
    """Measure the per-cell ceilings a requested matrix is bounded by.

    Args:
        batch_dir: Directory of batch_*.json files.
        judged_paths: judged JSONL path(s) supplying scorer_verdict.
        scorer: Target scorer name.
    Returns:
        MatrixCaps for that scorer. An unknown scorer yields (0, 0) rather than
        an error, so `--caps-only` can report it.
    """
    items = read_batch_items(batch_dir)
    positives, negatives = partition_by_verdict(items, read_verdicts(judged_paths), scorer)
    return MatrixCaps(
        scorer=scorer,
        positives_available=len(positives),
        negatives_available=len(negatives),
    )


def oracle_rows(
    batch_dir: Path,
    judged_paths: Sequence[Path],
    scorer: str,
    requested: RequestedMatrix,
) -> list[dict[str, Any]]:
    """Emit raw label rows reproducing `requested` exactly for `scorer`.

    Args:
        batch_dir: Directory of batch_*.json files from label-export.
        judged_paths: judged JSONL path(s) supplying the real scorer_verdicts.
        scorer: Target scorer name.
        requested: The confusion matrix to reproduce.
    Returns:
        Raw label rows (record_id, scorer, pre_label, notes) and nothing else —
        no output_text, no scorer_verdict, so label_import's contamination check
        passes.
    Raises:
        UnsatisfiableMatrixError: If the artifact holds too few rows, naming the
            per-cell caps. An unknown scorer has caps of (0, 0) and raises here
            rather than emitting an empty file.
        FileNotFoundError: If the batch dir holds no batches, or a judged path
            is absent.
    """
    items = read_batch_items(batch_dir)
    positives, negatives = partition_by_verdict(items, read_verdicts(judged_paths), scorer)
    caps = MatrixCaps(
        scorer=scorer,
        positives_available=len(positives),
        negatives_available=len(negatives),
    )
    if caps.cannot_satisfy(requested):
        raise UnsatisfiableMatrixError(requested, caps)
    return assign_labels(positives, negatives, scorer, requested)


def check_out_path(out_path: Path) -> None:
    """Refuse an output path that is the real human labels file.

    Args:
        out_path: Destination the CLI was asked to write.
    Returns:
        None.
    Raises:
        OracleOutputPathError: If the destination is named labels_v1.jsonl.
    """
    if out_path.name == _REAL_LABELS_FILENAME:
        raise OracleOutputPathError(out_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the oracle labeller."""
    p = argparse.ArgumentParser(
        prog="python scripts/oracle_labeller.py",
        description=(
            "Emit rule-based calibration labels with a known-by-construction "
            "confusion matrix, so the pipeline's kappa can be checked against a "
            "hand-computed value. NOT a labelling pass — the labels are synthetic."
        ),
    )
    p.add_argument("--batches", type=Path, default=ORACLE_BATCH_DIR, metavar="DIR",
                   help=f"Directory of batch_*.json files (default: {ORACLE_BATCH_DIR}).")
    p.add_argument("--judged", type=Path, required=True, nargs="+", metavar="PATH",
                   help="judged.jsonl and/or deterministic_judged.jsonl supplying scorer_verdict.")
    p.add_argument("--scorer", required=True, metavar="NAME",
                   help="Scorer to build the matrix for, e.g. refusal_judge.")
    p.add_argument("--tp", type=int, default=0, help="scorer=True,  human=True cell.")
    p.add_argument("--fp", type=int, default=0, help="scorer=True,  human=False cell.")
    p.add_argument("--fn", type=int, default=0, help="scorer=False, human=True cell.")
    p.add_argument("--tn", type=int, default=0, help="scorer=False, human=False cell.")
    p.add_argument("--out", type=Path, default=ORACLE_RAW_FILE, metavar="PATH",
                   help=f"Destination raw-labels JSONL (default: {ORACLE_RAW_FILE}).")
    p.add_argument("--caps-only", action="store_true",
                   help="Print the per-cell caps for --scorer and exit without writing.")
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the oracle labeller.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    Raises:
        OracleOutputPathError: If --out is the real human labels file.
        UnsatisfiableMatrixError: If the requested matrix exceeds the caps.
    """
    args = _build_parser().parse_args(argv)
    check_out_path(args.out)

    if args.caps_only:
        print(matrix_caps(args.batches, args.judged, args.scorer).model_dump_json(indent=2))
        return 0

    requested = RequestedMatrix(tp=args.tp, fp=args.fp, fn=args.fn, tn=args.tn)
    rows = oracle_rows(args.batches, args.judged, args.scorer, requested)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )
    print(
        f"Wrote {len(rows)} ORACLE label(s) for {args.scorer} "
        f"(tp={args.tp} fp={args.fp} fn={args.fn} tn={args.tn}) -> {args.out}\n"
        f"  Import with --model {ORACLE_MODEL_ID} and --out {ORACLE_LABELS_FILE}.\n"
        f"  These are synthetic labels; they measure the pipeline, not a scorer.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
