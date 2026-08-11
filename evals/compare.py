"""
Module: compare
Layer: evals (utility)
Purpose: compare verb — load two generation directories, aggregate judged records into
         CaseStat tuples, inner-join on case_id, run McNemar paired test, and print the
         verdict with per-case delta table. Cases present in one run but absent from the
         other are named explicitly — a silently shrunken denominator is the failure mode
         this module is designed to catch.
Dependencies: argparse, json, logging, pathlib, sys, collections; pydantic; case_stats (classify),
              rate_stats (pass_rate, wilson_interval), paired_stats (paired_compare, PairedResult)
Used by: Makefile eval-compare target; tests/unit/evals/test_compare.py; evals/__main__.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, ConfigDict

from case_stats import CaseStat, classify, classify_battery
from paired_stats import PairedResult, paired_compare
from rate_stats import pass_rate, wilson_interval

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_JUDGED_FILE: str = "judged.jsonl"
_META_FILE: str = "meta.json"
_ENCODING: str = "utf-8"
_SORT_ORDER: dict[str, int] = {"regressed": 0, "improved": 1, "unchanged": 2}

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class _JudgedRow(BaseModel):
    """Minimal model for one row of judged.jsonl — only fields compare needs.

    Both record_id and case_id are present in judged.jsonl. case_id is the
    case-level grouping key; record_id identifies the expectation slot
    (case_id:kind:index) and is retained for tracing.

    Extra fields (judge_kind, score, detail, judge_model, repetition)
    are present in the file but ignored here.

    Attributes:
        record_id: Stable slot ID, e.g. 'case_001:tone_judge:0'.
        case_id: The case this slot belongs to, e.g. 'case_001'.
        passed: Whether the eval slot passed after polarity was applied.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    record_id: str
    case_id: str
    passed: bool


class CaseDelta(BaseModel):
    """Per-case pass-rate delta between two eval runs.

    Attributes:
        case_id: The record_id (eval slot identifier).
        before_passes: Pass count in the reference run.
        before_k: Repetition count in the reference run.
        before_rate: Raw pass rate in the reference run.
        after_passes: Pass count in the candidate run.
        after_k: Repetition count in the candidate run.
        after_rate: Raw pass rate in the candidate run.
        change: Direction of majority-vote binary change.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    before_passes: int
    before_k: int
    before_rate: float
    after_passes: int
    after_k: int
    after_rate: float
    change: Literal["improved", "regressed", "unchanged"]


class CompareResult(BaseModel):
    """Full comparison result between two eval generation runs.

    Attributes:
        before_gen_id: Identifier of the reference generation run.
        after_gen_id: Identifier of the candidate generation run.
        intersection_size: Number of case_ids present in both runs.
        only_in_before: Sorted tuple of case_ids present only in the reference run.
        only_in_after: Sorted tuple of case_ids present only in the candidate run.
        case_deltas: Per-case delta table sorted regressions first.
        paired_result: McNemar test result over the matched cases.
    """

    model_config = ConfigDict(frozen=True)

    before_gen_id: str
    after_gen_id: str
    intersection_size: int
    only_in_before: tuple[str, ...]
    only_in_after: tuple[str, ...]
    case_deltas: tuple[CaseDelta, ...]
    paired_result: PairedResult


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _read_judged_rows(gen_dir: Path) -> list[_JudgedRow]:
    """Parse judged.jsonl from a generation directory, raising on malformed lines.

    Args:
        gen_dir: Directory containing judged.jsonl (created by eval-judge pass).
    Returns:
        Parsed _JudgedRow list; empty list if file absent or unreadable.
    Raises:
        ValueError: If any line fails pydantic validation — a corrupt row must not
            silently shrink the denominator compare relies on.
    """
    path = gen_dir / _JUDGED_FILE
    if not path.exists():
        return []
    rows: list[_JudgedRow] = []
    for line in path.read_text(encoding=_ENCODING).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(_JudgedRow.model_validate_json(stripped))
        except Exception as exc:
            raise ValueError(
                f"malformed judged row in {path}: {stripped[:80]!r}"
            ) from exc
    return rows


def _build_case_stats(rows: Sequence[_JudgedRow]) -> tuple[CaseStat, ...]:
    """Group _JudgedRow objects by case_id and compute per-case CaseStat.

    Groups by case_id (not record_id / expectation slot) so that all k records
    for a case — across all judge kinds and repetitions — contribute to one
    CaseStat. Grouping by record_id (the old behaviour) created one CaseStat
    per slot, inflating the McNemar denominator with correlated pairs.

    Args:
        rows: Parsed judged.jsonl rows for one generation run.
    Returns:
        Tuple of CaseStat, one per unique case_id, unsorted.
    """
    groups: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        groups[row.case_id].append(row.passed)

    stats: list[CaseStat] = []
    for case_id, passed_list in groups.items():
        k = len(passed_list)
        passes = sum(1 for p in passed_list if p)
        rate = pass_rate(passes, k)
        ci_low, ci_high = wilson_interval(passes, k)
        stats.append(
            CaseStat(
                case_id=case_id,
                k=k,
                passes=passes,
                pass_rate=rate,
                ci_low=ci_low,
                ci_high=ci_high,
                classification=classify(passes, k),
            )
        )
    return tuple(stats)


def _read_gen_id(gen_dir: Path) -> str:
    """Read gen_id from meta.json, falling back to the directory name.

    Args:
        gen_dir: Generation directory (may or may not contain meta.json).
    Returns:
        gen_id string.
    """
    meta_path = gen_dir / _META_FILE
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding=_ENCODING))
            return str(meta.get("gen_id", gen_dir.name))
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning("meta.json unreadable in %s: %s — using directory name as gen_id", gen_dir, exc)
    return gen_dir.name


# ---------------------------------------------------------------------------
# Compare logic
# ---------------------------------------------------------------------------


def _change_direction(before: CaseStat, after: CaseStat) -> Literal["improved", "regressed", "unchanged"]:
    """Compute binary change direction using majority-vote pass (passes * 2 > k).

    Args:
        before: Reference run stat.
        after: Candidate run stat.
    Returns:
        'improved' if fail→pass, 'regressed' if pass→fail, 'unchanged' otherwise.
    """
    before_pass = before.passes * 2 > before.k
    after_pass = after.passes * 2 > after.k
    if not before_pass and after_pass:
        return "improved"
    if before_pass and not after_pass:
        return "regressed"
    return "unchanged"


def _build_delta_table(
    before_map: dict[str, CaseStat],
    after_map: dict[str, CaseStat],
) -> tuple[CaseDelta, ...]:
    """Build per-case delta table for the inner join, sorted regressions first.

    Args:
        before_map: case_id → CaseStat from reference run.
        after_map: case_id → CaseStat from candidate run.
    Returns:
        Tuple of CaseDelta for cases in both runs, sorted by change direction.
    """
    deltas: list[CaseDelta] = []
    for case_id, bef in before_map.items():
        if case_id not in after_map:
            continue
        aft = after_map[case_id]
        change = _change_direction(bef, aft)
        deltas.append(
            CaseDelta(
                case_id=case_id,
                before_passes=bef.passes,
                before_k=bef.k,
                before_rate=bef.pass_rate,
                after_passes=aft.passes,
                after_k=aft.k,
                after_rate=aft.pass_rate,
                change=change,
            )
        )
    deltas.sort(key=lambda d: _SORT_ORDER[d.change])
    return tuple(deltas)


def _detect_evasion(case_deltas: tuple[CaseDelta, ...]) -> bool:
    """Return True when capability net-regresses while guard net-improves.

    Counts per-battery change directions from the per-case delta table.
    Cases whose case_id prefix matches neither battery are silently skipped
    (they don't contribute to the evasion signal).

    Evasion fires when:
      capability regressions > capability improvements   (cap fell)
      AND guard improvements > guard regressions         (guard rose)

    Args:
        case_deltas: Per-case delta table from _build_delta_table.
    Returns:
        True if the evasion pattern is present, False otherwise.
    """
    cap_regressions = cap_improvements = 0
    guard_improvements = guard_regressions = 0
    for d in case_deltas:
        try:
            battery = classify_battery(d.case_id)
        except ValueError as exc:
            _logger.warning("classify_battery(%r) failed: %s — excluded from evasion analysis", d.case_id, exc)
            continue
        if battery == "capability":
            if d.change == "regressed":
                cap_regressions += 1
            elif d.change == "improved":
                cap_improvements += 1
        else:
            if d.change == "improved":
                guard_improvements += 1
            elif d.change == "regressed":
                guard_regressions += 1
    cap_net_regressed = cap_regressions > cap_improvements
    guard_net_improved = guard_improvements > guard_regressions
    return cap_net_regressed and guard_net_improved


def compare_runs(before_dir: Path, after_dir: Path) -> CompareResult:
    """Compare two eval generation directories using a McNemar paired test.

    Loads judged.jsonl from each directory, aggregates into CaseStat tuples,
    inner-joins on case_id, and runs paired_compare. Cases in only one run
    appear in only_in_before or only_in_after — never silently dropped.

    Args:
        before_dir: Reference generation directory.
        after_dir: Candidate generation directory.
    Returns:
        CompareResult with intersection stats, missing cases, delta table, and verdict.
    """
    before_gen_id = _read_gen_id(before_dir)
    after_gen_id = _read_gen_id(after_dir)

    before_stats = _build_case_stats(_read_judged_rows(before_dir))
    after_stats = _build_case_stats(_read_judged_rows(after_dir))

    before_map: dict[str, CaseStat] = {s.case_id: s for s in before_stats}
    after_map: dict[str, CaseStat] = {s.case_id: s for s in after_stats}

    before_ids = frozenset(before_map)
    after_ids = frozenset(after_map)
    only_in_before = tuple(sorted(before_ids - after_ids))
    only_in_after = tuple(sorted(after_ids - before_ids))
    intersection_size = len(before_ids & after_ids)

    paired_result = paired_compare(before_stats, after_stats)
    case_deltas = _build_delta_table(before_map, after_map)

    if _detect_evasion(case_deltas):
        paired_result = PairedResult(
            improved=paired_result.improved,
            regressed=paired_result.regressed,
            unchanged=paired_result.unchanged,
            p_value=paired_result.p_value,
            verdict="regression_evasion",
        )

    return CompareResult(
        before_gen_id=before_gen_id,
        after_gen_id=after_gen_id,
        intersection_size=intersection_size,
        only_in_before=only_in_before,
        only_in_after=only_in_after,
        case_deltas=case_deltas,
        paired_result=paired_result,
    )


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_report(result: CompareResult) -> list[str]:
    """Format a CompareResult as human-readable report lines.

    Prints: header with gen_ids, intersection size, missing-case lists, verdict
    with p-value, discordant counts, and per-case delta table (k of both runs
    adjacent to every rate, regressions first).

    Args:
        result: CompareResult from compare_runs.
    Returns:
        List of output lines (no trailing newline per line).
    """
    pr = result.paired_result
    lines: list[str] = [
        f"Comparing {result.before_gen_id} → {result.after_gen_id}",
        f"Intersection: {result.intersection_size} cases",
    ]
    if result.only_in_before:
        lines.append(
            f"Only in before ({len(result.only_in_before)}): {', '.join(result.only_in_before)}"
        )
    if result.only_in_after:
        lines.append(
            f"Only in after ({len(result.only_in_after)}): {', '.join(result.only_in_after)}"
        )
    lines.append("")
    lines.append(
        f"Verdict: {pr.verdict.upper()}  p={pr.p_value:.4f}"
        f"  improved={pr.improved}  regressed={pr.regressed}  unchanged={pr.unchanged}"
    )
    lines.append("")
    header = f"{'case_id':<50} {'before':>14} {'after':>14}  change"
    lines.append(header)
    lines.append("-" * len(header))
    for d in result.case_deltas:
        bef = f"{d.before_passes}/{d.before_k} ({d.before_rate:.2f})"
        aft = f"{d.after_passes}/{d.after_k} ({d.after_rate:.2f})"
        lines.append(f"{d.case_id:<50} {bef:>14} {aft:>14}  {d.change}")
    return lines


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `python -m evals compare`.

    Args:
        argv: CLI arguments; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Compare two eval generation directories with McNemar paired test."
    )
    parser.add_argument("--before", required=True, type=Path, help="Reference generation directory.")
    parser.add_argument("--after", required=True, type=Path, help="Candidate generation directory.")
    args = parser.parse_args(argv)

    for label, path in (("before", args.before), ("after", args.after)):
        if not path.is_dir():
            print(f"ERROR: {label} directory not found: {path}", file=sys.stderr)
            return 1

    result = compare_runs(args.before, args.after)
    for line in format_report(result):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
