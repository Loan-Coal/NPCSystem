"""
Module: mock_labeller
Layer: scripts (dev tooling — not part of src/ or the evals package)
Purpose: Emit schema-valid but MEANINGLESS calibration labels so the
         export → import → adjudicate → calibrate pipeline can be exercised
         end to end without spending Claude credits. Deterministic under a seed.
Dependencies: argparse, json, pathlib, random, sys
Used by: make mock-label (pipeline smoke testing only)
Does NOT: call any LLM, read scorer verdicts, or produce usable calibration data

WARNING — these labels are random. They exist to prove the plumbing moves data
of the right shape, never to measure scorer quality. Every note is prefixed
MOCK: and the intended --model identifier is 'mock-random-v1', so mock rows are
greppable and can never be mistaken for a real labelling pass. A calibration
report built on these is meaningless by construction: expect kappa near 0.
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

MOCK_MODEL_ID: str = "mock-random-v1"
_NOTE_PREFIX: str = "MOCK:"
_DEFAULT_SEED: int = 1729
_DEFAULT_TRUE_RATE: float = 0.7
_NOTE_MAX_CHARS: int = 140


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def mock_row(item: dict[str, Any], rng: random.Random, true_rate: float) -> dict[str, Any]:
    """Build one random-but-valid raw label row for an export item.

    Mirrors the four-field contract LABEL_PROMPT.md specifies, so the output is
    byte-compatible with a real labelling session.

    Args:
        item: One item from an export batch file.
        rng: Seeded RNG, so a given seed reproduces the same labels exactly.
        true_rate: Probability of emitting pre_label=True.
    Returns:
        Dict with record_id, scorer, pre_label, notes.
    """
    scorer = item.get("scorer", "unknown")
    note = f"{_NOTE_PREFIX} random label for {scorer}; not a real judgment"
    return {
        "record_id": item["record_id"],
        "scorer": scorer,
        "pre_label": rng.random() < true_rate,
        "notes": note[:_NOTE_MAX_CHARS],
    }


def label_batches(batch_dir: Path, seed: int, true_rate: float) -> list[dict[str, Any]]:
    """Generate mock rows for every batch file in a directory.

    Args:
        batch_dir: Directory holding batch_*.json files from label-export.
        seed: RNG seed for reproducibility.
        true_rate: Probability of pre_label=True.
    Returns:
        Mock label rows in batch-file order.
    Raises:
        FileNotFoundError: If no batch files are found.
    """
    paths = sorted(batch_dir.glob("batch_*.json"))
    if not paths:
        raise FileNotFoundError(f"No batch_*.json files found in {batch_dir}")

    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for path in paths:
        items = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(mock_row(item, rng, true_rate) for item in items)
    return rows


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the mock labeller."""
    p = argparse.ArgumentParser(
        prog="python scripts/mock_labeller.py",
        description=(
            "Emit random, schema-valid calibration labels for pipeline testing. "
            "NOT a substitute for real labelling — the resulting artifact is meaningless."
        ),
    )
    p.add_argument("--batches", type=Path, required=True, metavar="DIR",
                   help="Directory of batch_*.json files from label-export.")
    p.add_argument("--out", type=Path, required=True, metavar="PATH",
                   help="Destination raw-labels JSONL path.")
    p.add_argument("--seed", type=int, default=_DEFAULT_SEED, metavar="N",
                   help=f"RNG seed (default: {_DEFAULT_SEED}).")
    p.add_argument("--true-rate", type=float, default=_DEFAULT_TRUE_RATE, metavar="P",
                   help=f"P(pre_label=True) (default: {_DEFAULT_TRUE_RATE}).")
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the mock labeller.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    """
    args = _build_parser().parse_args(argv)

    rows = label_batches(args.batches, args.seed, args.true_rate)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
        encoding="utf-8",
    )

    print(
        f"WARNING: wrote {len(rows)} MOCK label(s) (seed={args.seed}) → {args.out}\n"
        f"         These are random. Import with --model {MOCK_MODEL_ID} and never "
        f"treat the resulting calibration report as real.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
