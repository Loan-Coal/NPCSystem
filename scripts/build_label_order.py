"""
Module: build_label_order
Layer: scripts (dev tooling)
Purpose: CLI wiring for evals/label_sampling.py — turn a generation directory's
         verdict files into a stratified labelling order plus a coverage-gap
         report (EVAL-P22.1). Replaces the session-scratchpad glue this task
         found stranded outside the repo.
Dependencies: argparse, json, pathlib, sys; evals/label_sampling
Used by: project-harness/Run-OvernightCombined.ps1, operators

WHY IT WARNS LOUDLY ON A MISSING judged.jsonl
The scratchpad version silently produced a deterministic-only ordering when a
generation directory had no LLM-judge verdicts, while still calling its output a
full-corpus labelling order. That is the same silent-omission shape as ISSUE-180
and ISSUE-181. Here, a missing or empty verdict source is reported on stderr and
reflected in the printed summary; --require-both turns it into a hard failure for
unattended runs that must not produce a partial artifact unnoticed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from label_sampling import coverage_report, order_for_labelling  # noqa: E402

# Fixed so the same gen dir always yields the same order; matches the DEC-176
# seed-work convention of logging/pinning every RNG seed the harness uses.
_SEED: int = 20260817

_JUDGED_FILE: str = "judged.jsonl"
_DETERMINISTIC_FILE: str = "deterministic_judged.jsonl"
_ORDER_SUFFIX: str = ".order.txt"
_GAPS_SUFFIX: str = ".coverage_gaps.txt"
_NO_GAPS_TEXT: str = "(none -- every scorer has both verdicts)"


def _read_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, returning [] when it does not exist."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def collect_rows(gen_dir: Path) -> tuple[list[tuple[str, str, bool]], list[str]]:
    """Build (key, scorer, verdict) triples from both verdict sources.

    Args:
        gen_dir: A generation directory containing judged.jsonl and/or
            deterministic_judged.jsonl.
    Returns:
        (rows, warnings) — warnings names each verdict source that was absent or
        empty, so a partial corpus is never reported as a whole one.
    """
    judged = _read_jsonl(gen_dir / _JUDGED_FILE)
    deterministic = _read_jsonl(gen_dir / _DETERMINISTIC_FILE)

    warnings: list[str] = []
    if not judged:
        warnings.append(
            f"{_JUDGED_FILE} is missing or empty — the ordering covers NO LLM-judge "
            "rows (tone_judge / affirms_judge / refusal_judge). Run a judge pass first."
        )
    if not deterministic:
        warnings.append(
            f"{_DETERMINISTIC_FILE} is missing or empty — the ordering covers NO "
            "deterministic matcher rows. Run the deterministic-verdicts pass first."
        )

    rows: list[tuple[str, str, bool]] = []
    for row in judged:
        rows.append((row["record_id"], row["judge_kind"], bool(row["score"])))
    for row in deterministic:
        rows.append((row["record_id"], row["matcher_kind"], bool(row["score"])))
    return rows, warnings


def build(gen_dir: Path, out_prefix: Path, *, require_both: bool) -> int:
    """Write the labelling order and coverage-gap report for one generation dir.

    Args:
        gen_dir: Generation directory to read verdicts from.
        out_prefix: Output path prefix; '.order.txt' and '.coverage_gaps.txt'
            are appended.
        require_both: Fail rather than emit a partial ordering when either
            verdict source is missing.
    Returns:
        0 on success, 1 when there is nothing to order or a required source is
        missing.
    """
    rows, warnings = collect_rows(gen_dir)
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if not rows:
        print(f"No verdict rows found under {gen_dir}.", file=sys.stderr)
        return 1
    if warnings and require_both:
        print("--require-both set and a verdict source is missing — refusing to write a partial ordering.", file=sys.stderr)
        return 1

    order = order_for_labelling(rows, seed=_SEED)
    gaps = coverage_report(rows)

    order_path = out_prefix.with_suffix(_ORDER_SUFFIX)
    order_path.parent.mkdir(parents=True, exist_ok=True)
    order_path.write_text("\n".join(order), encoding="utf-8")

    gaps_path = out_prefix.with_suffix(_GAPS_SUFFIX)
    gaps_path.write_text("\n".join(gaps) if gaps else _NO_GAPS_TEXT, encoding="utf-8")

    scope = "PARTIAL" if warnings else "full"
    print(f"rows: {len(rows)}  ordered keys: {len(order)}  coverage gaps: {len(gaps)}  scope: {scope}")
    print(f"order written to: {order_path}")
    print(f"coverage gaps written to: {gaps_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and build the labelling order."""
    parser = argparse.ArgumentParser(
        description="Build a stratified labelling order and coverage-gap report (EVAL-P22.1)."
    )
    parser.add_argument("gen_dir", type=Path, help="evals/generations/<gen_id>/")
    parser.add_argument("out_prefix", type=Path, help="Output path prefix (suffixes are appended).")
    parser.add_argument(
        "--require-both",
        action="store_true",
        help="Fail instead of emitting a partial ordering when a verdict source is missing.",
    )
    args = parser.parse_args(argv)
    return build(args.gen_dir, args.out_prefix, require_both=args.require_both)


if __name__ == "__main__":
    sys.exit(main())
