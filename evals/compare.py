"""
Module: compare
Layer: evals (utility)
Purpose: compare verb — load two generation directories, aggregate judged records into
         CaseStat tuples, inner-join on case_id, run McNemar paired test, and print the
         verdict with per-case delta table. Cases present in one run but absent from the
         other are named explicitly — a silently shrunken denominator is the failure mode
         this module is designed to catch. Refuses (non-zero exit) rather than reporting a
         confident verdict when the two runs are not actually comparable: empty
         intersection, or a mismatched harness_version / judge_model / k (EVAL-P18.3).
Dependencies: argparse, json, logging, pathlib, sys, collections; pydantic; case_stats (classify),
              rate_stats (pass_rate, wilson_interval), paired_stats (paired_compare, PairedResult),
              tier_attribution (read_tier_spend, format_tier_spend — per-arm context attribution)
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
from judge_identity import resolve_judge_identity
from run_variance import VARIANT_FIELDS, describe_variant_delta
from paired_stats import PairedResult, paired_compare
from rate_stats import pass_rate, wilson_interval
from context_receipt_record import TierSpendRecord
from tier_attribution import format_tier_spend, read_tier_spend
from verdict_sources import VerdictRow, load_unified_rows, source_counts

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_META_FILE: str = "meta.json"
_ENCODING: str = "utf-8"
_SORT_ORDER: dict[str, int] = {"regressed": 0, "improved": 1, "unchanged": 2}
_CONFIG_KEY: str = "config"
_GEN_ID_KEY: str = "gen_id"
_K_KEY: str = "k"
_HARNESS_VERSION_KEY: str = "harness_version"
_JUDGE_MODEL_KEY: str = "judge_model"

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


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


class RunMeta(BaseModel):
    """Comparability-relevant identity read from one generation directory's meta.json.

    Attributes:
        gen_id: Identifier of the run (from meta.json, falling back to the directory name).
        harness_version: Comparability hash from EVAL-P18.1 (edits to case files, judge
            criteria, or matchers.py change it). None when meta.json predates that field
            or is absent entirely — treated as a value like any other for equality, so two
            runs that both lack it are not silently assumed comparable on that basis alone.
        judge_model: The judge identity that ACTUALLY scored this run, resolved by
            judge_identity.resolve_judge_identity — 'panel:<sorted roster>' for a
            panel pass, a model tag for a single-judge pass. Falls back to
            meta.json's generation-time config.judge_model for directories written
            before run_status.json existed (DEC-189). None when unrecorded.
            Reading the real pass rather than the configured model is what lets the
            gate see a panel-vs-single-judge mismatch at all (ISSUE-185).
        k: Repetition count this run was generated at. None when unrecorded.
    """

    model_config = ConfigDict(frozen=True)

    gen_id: str
    harness_version: str | None = None
    judge_model: str | None = None
    k: int | None = None
    # Variant fields — EXPECTED to differ between arms, so deliberately NOT part of
    # _comparability_error. They are the independent variable; reporting them is what
    # keeps a McNemar verdict attached to the right cause.
    variant: dict[str, object] = {}


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
        before_meta: Comparability identity (harness_version, judge_model, k) of the
            reference run.
        after_meta: Comparability identity of the candidate run.
        refusal_reason: None when the two runs are comparable. Otherwise, a human-readable
            reason `main()` uses to exit non-zero instead of printing a confident verdict
            (EVAL-P18.3): empty intersection, or a mismatched harness_version, judge_model,
            or k.
    """

    model_config = ConfigDict(frozen=True)

    before_gen_id: str
    after_gen_id: str
    intersection_size: int
    only_in_before: tuple[str, ...]
    only_in_after: tuple[str, ...]
    case_deltas: tuple[CaseDelta, ...]
    paired_result: PairedResult
    before_judged_slots: int = 0
    before_det_slots: int = 0
    after_judged_slots: int = 0
    after_det_slots: int = 0
    before_meta: RunMeta
    after_meta: RunMeta
    # Per-tier attribution of the context that ACTUALLY reached the model in each arm, from
    # the engine's own receipts. Defaults to () so an arm with no transcript still builds.
    before_tier_spend: tuple[TierSpendRecord, ...] = ()
    after_tier_spend: tuple[TierSpendRecord, ...] = ()
    refusal_reason: str | None = None


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _build_case_stats(rows: Sequence[VerdictRow]) -> tuple[CaseStat, ...]:
    """Group VerdictRow objects by case_id and compute per-case CaseStat.

    Groups by case_id (not record_id / expectation slot) so that all k records
    for a case — across all judge kinds, matcher kinds, and repetitions — contribute
    to one CaseStat. Both judged.jsonl and deterministic_judged.jsonl rows are
    included via load_unified_rows before this function is called.

    Args:
        rows: Unified VerdictRow list from load_unified_rows (both verdict sources).
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


def _read_run_meta(gen_dir: Path) -> RunMeta:
    """Read comparability identity from a generation directory's meta.json.

    Args:
        gen_dir: Generation directory (may or may not contain meta.json).
    Returns:
        RunMeta with gen_id falling back to the directory name, and harness_version /
        judge_model / k as None when meta.json is absent, unreadable, or predates
        EVAL-P18.1/P18.2 (no config.harness_version / config.judge_model / top-level k).
        judge_model is resolved from run_status.json when present (ISSUE-185).
    """
    meta_path = gen_dir / _META_FILE
    if not meta_path.exists():
        return RunMeta(gen_id=gen_dir.name, judge_model=resolve_judge_identity(gen_dir, None))
    try:
        meta = json.loads(meta_path.read_text(encoding=_ENCODING))
    except (json.JSONDecodeError, OSError) as exc:
        _logger.warning("meta.json unreadable in %s: %s — comparability fields unknown", gen_dir, exc)
        return RunMeta(gen_id=gen_dir.name)
    config = meta.get(_CONFIG_KEY, {})
    return RunMeta(
        gen_id=str(meta.get(_GEN_ID_KEY, gen_dir.name)),
        harness_version=config.get(_HARNESS_VERSION_KEY),
        judge_model=resolve_judge_identity(gen_dir, config.get(_JUDGE_MODEL_KEY)),
        k=meta.get(_K_KEY),
        variant={field: config[field] for field in VARIANT_FIELDS if field in config},
    )


def _comparability_error(before: RunMeta, after: RunMeta, intersection_size: int) -> str | None:
    """Return a refusal reason when two runs are not safely comparable, else None.

    Checked in order: empty intersection first (the cheapest and most severe defect —
    a verdict over zero shared cases), then harness_version, judge identity, and k
    mismatch. The judge identity is the pass that actually ran (panel roster or single
    model), not the generation-time configured model — see judge_identity (ISSUE-185).

    Args:
        before: Reference run's comparability identity.
        after: Candidate run's comparability identity.
        intersection_size: Number of case_ids present in both runs.
    Returns:
        A human-readable refusal reason, or None when the runs are comparable.
    """
    if intersection_size == 0:
        return "empty intersection — no case_ids are shared between the two runs"
    if before.harness_version != after.harness_version:
        return (
            f"harness_version mismatch: before={before.harness_version!r} "
            f"after={after.harness_version!r}"
        )
    if before.judge_model != after.judge_model:
        return (
            f"judge mismatch: before={before.judge_model!r} after={after.judge_model!r} — "
            "the two arms were scored by different judge passes, so any delta between "
            "them is partly the measuring instrument changing, not the engine (ISSUE-185)"
        )
    if before.k != after.k:
        return f"k mismatch: before={before.k!r} after={after.k!r}"
    return None


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

    Loads both judged.jsonl and deterministic_judged.jsonl from each directory,
    aggregates into CaseStat tuples, inner-joins on case_id, and runs paired_compare.
    Cases present in only one run appear in only_in_before or only_in_after — never
    silently dropped.

    Args:
        before_dir: Reference generation directory.
        after_dir: Candidate generation directory.
    Returns:
        CompareResult with intersection stats, per-source slot counts, missing cases,
        delta table, verdict, run identities, and a refusal_reason (EVAL-P18.3) that is
        non-None when the two runs are not safely comparable.
    """
    before_meta = _read_run_meta(before_dir)
    after_meta = _read_run_meta(after_dir)

    before_rows = load_unified_rows(before_dir)
    after_rows = load_unified_rows(after_dir)
    before_sc = source_counts(before_rows)
    after_sc = source_counts(after_rows)

    before_stats = _build_case_stats(before_rows)
    after_stats = _build_case_stats(after_rows)

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
        before_gen_id=before_meta.gen_id,
        after_gen_id=after_meta.gen_id,
        intersection_size=intersection_size,
        only_in_before=only_in_before,
        only_in_after=only_in_after,
        case_deltas=case_deltas,
        paired_result=paired_result,
        before_judged_slots=before_sc.get("judged", 0),
        before_det_slots=before_sc.get("deterministic", 0),
        after_judged_slots=after_sc.get("judged", 0),
        after_det_slots=after_sc.get("deterministic", 0),
        before_meta=before_meta,
        after_meta=after_meta,
        before_tier_spend=read_tier_spend(before_dir),
        after_tier_spend=read_tier_spend(after_dir),
        refusal_reason=_comparability_error(before_meta, after_meta, intersection_size),
    )


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _format_header(result: CompareResult) -> list[str]:
    """Build the report header lines: gen_ids, source counts, missing cases.

    Args:
        result: CompareResult from compare_runs.
    Returns:
        Header lines including per-source slot counts for both runs.
    """
    lines: list[str] = [
        f"Comparing {result.before_gen_id} → {result.after_gen_id}",
        f"Intersection: {result.intersection_size} cases",
        (
            f"Sources (before): {result.before_judged_slots} judged"
            f" + {result.before_det_slots} deterministic"
            f" = {result.before_judged_slots + result.before_det_slots} slots"
        ),
        (
            f"Sources (after):  {result.after_judged_slots} judged"
            f" + {result.after_det_slots} deterministic"
            f" = {result.after_judged_slots + result.after_det_slots} slots"
        ),
    ]
    if result.only_in_before:
        lines.append(
            f"Only in before ({len(result.only_in_before)}): {', '.join(result.only_in_before)}"
        )
    if result.only_in_after:
        lines.append(
            f"Only in after ({len(result.only_in_after)}): {', '.join(result.only_in_after)}"
        )
    lines.append(_format_run_meta("before", result.before_meta))
    lines.append(f"Tiers  (before): {format_tier_spend(result.before_tier_spend)}")
    lines.append(_format_run_meta("after", result.after_meta))
    lines.append(f"Tiers  (after):  {format_tier_spend(result.after_tier_spend)}")
    if result.refusal_reason is not None:
        lines.append(f"REFUSED: {result.refusal_reason}")
    return lines


def _format_run_meta(label: str, meta: RunMeta) -> str:
    """Format one run's comparability identity as a single header line.

    Args:
        label: 'before' or 'after'.
        meta: The run's RunMeta.
    Returns:
        A single formatted line, e.g. 'Config (before): harness_version=... judge_model=... k=...'.
    """
    variant = " ".join(f"{k}={v!r}" for k, v in sorted(meta.variant.items()))
    return (
        f"Config ({label}): harness_version={meta.harness_version!r} "
        f"judge_model={meta.judge_model!r} k={meta.k!r}"
        + (f" {variant}" if variant else "")
    )


def format_report(result: CompareResult) -> list[str]:
    """Format a CompareResult as human-readable report lines.

    Prints: header with gen_ids, per-source slot counts, intersection size,
    missing-case lists, verdict with p-value, discordant counts, and per-case
    delta table (k of both runs adjacent to every rate, regressions first).

    Args:
        result: CompareResult from compare_runs.
    Returns:
        List of output lines (no trailing newline per line).
    """
    pr = result.paired_result
    lines = _format_header(result)
    lines.append("")
    # What was deliberately varied. Stated even when nothing differs: a blank reads as
    # "not checked", and two arms that turn out identical is itself a finding.
    lines.append(
        f"Differs: {describe_variant_delta(result.before_meta.variant, result.after_meta.variant)}"
    )
    lines.append("")
    lines.append(
        f"Verdict: {pr.verdict.upper()}  p={pr.p_value:.4f}"
        f"  improved={pr.improved}  regressed={pr.regressed}  unchanged={pr.unchanged}"
    )
    lines.append("")
    col_header = f"{'case_id':<50} {'before':>14} {'after':>14}  change"
    lines.append(col_header)
    lines.append("-" * len(col_header))
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
        0 on success. 1 if a directory is missing, or if the two runs are not comparable
        (empty intersection, or a mismatched harness_version / judge_model / k — EVAL-P18.3):
        refusing beats printing a confident verdict over nothing.
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
    if result.refusal_reason is not None:
        print(f"ERROR: refusing incomparable runs — {result.refusal_reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
