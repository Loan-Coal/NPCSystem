"""
Module: mock_adjudicate
Layer: scripts (dev tooling — not part of src/ or the evals package)
Purpose: Fill human_verdict on a labels JSONL with random values so the final
         calibrate stage (confusion matrices, Cohen's kappa, bootstrap CI) can be
         exercised without a 4-6 hour human adjudication pass. Deterministic
         under a seed.
Dependencies: argparse, json, pathlib, random, sys
Used by: make mock-calibrate (pipeline smoke testing only)
Does NOT: call any LLM, or produce usable calibration data

WARNING — verdicts are random, so the resulting kappa measures nothing. This
exists to prove the arithmetic and reporting stages run end to end. Every row it
touches is stamped adjudicated_at='MOCK' and its notes prefixed MOCK:, so mock
rows are greppable and can never be mistaken for real adjudication.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOCK_TIMESTAMP: str = "MOCK"
_NOTE_PREFIX: str = "MOCK:"
_DEFAULT_SEED: int = 4242
_DEFAULT_AGREE_RATE: float = 0.85


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def adjudicate_row(row: dict[str, Any], rng: random.Random, agree_rate: float) -> dict[str, Any]:
    """Stamp one label row with a random human_verdict.

    The verdict agrees with scorer_verdict at `agree_rate`, so the resulting
    confusion matrix is non-degenerate (a constant verdict yields undefined
    kappa and would not exercise the CI code path).

    Args:
        row: One CalibrationLabel row as a dict.
        rng: Seeded RNG for reproducibility.
        agree_rate: Probability the mock verdict matches scorer_verdict.
    Returns:
        A new dict with human_verdict, adjudicated_at, and notes set.
    """
    scorer_verdict = bool(row.get("scorer_verdict", False))
    verdict = scorer_verdict if rng.random() < agree_rate else not scorer_verdict
    notes = str(row.get("notes", ""))
    if not notes.startswith(_NOTE_PREFIX):
        notes = f"{_NOTE_PREFIX} {notes}".strip()
    return {**row, "human_verdict": verdict, "adjudicated_at": MOCK_TIMESTAMP, "notes": notes}


def adjudicate_file(path: Path, seed: int, agree_rate: float) -> list[dict[str, Any]]:
    """Apply mock adjudication to every row of a labels JSONL file.

    Args:
        path: Path to the labels JSONL written by label-import.
        seed: RNG seed for reproducibility.
        agree_rate: Probability the mock verdict matches scorer_verdict.
    Returns:
        Adjudicated rows in file order.
    Raises:
        FileNotFoundError: If the path does not exist.
    """
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(adjudicate_row(json.loads(line), rng, agree_rate))
    return rows


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the mock adjudicator."""
    p = argparse.ArgumentParser(
        prog="python scripts/mock_adjudicate.py",
        description=(
            "Fill human_verdict with random values for pipeline testing. "
            "NOT a substitute for real adjudication — the resulting kappa is meaningless."
        ),
    )
    p.add_argument("--labels", type=Path, required=True, metavar="PATH",
                   help="Labels JSONL from label-import.")
    p.add_argument("--out", type=Path, required=True, metavar="PATH",
                   help="Destination adjudicated JSONL path.")
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED, metavar="N",
                   help=f"RNG seed (default: {_DEFAULT_SEED}).")
    p.add_argument("--agree-rate", type=float, default=_DEFAULT_AGREE_RATE, metavar="P",
                   help=f"P(verdict agrees with scorer) (default: {_DEFAULT_AGREE_RATE}).")
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the mock adjudicator.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    """
    args = _build_parser().parse_args(argv)

    rows = adjudicate_file(args.labels, args.seed, args.agree_rate)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )

    print(
        f"WARNING: mock-adjudicated {len(rows)} row(s) (seed={args.seed}) -> {args.out}\n"
        f"         Verdicts are random; the calibration report from this file is meaningless.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
