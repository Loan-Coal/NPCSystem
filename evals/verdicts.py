"""
Module: verdicts
Layer: evals (eval harness — not part of src/)
Purpose: Persist the raw per-case verdicts of a completed eval run as JSON, so a later
         change to the headline denominator is a recomputation rather than an orphaned
         baseline (DEC-153 §7).
Dependencies: stdlib only (json, pathlib, typing).
Used by: runner.py and anti_hallucination_runner.py (--json-out), EVAL-P0.4 baseline.
Does NOT: import from src/npc_engine/, call any LLM, decide pass/fail (it only records).

Why counts are not enough: both runners report a skipped case as ``passed=True``, so the
published "41/53" folds skips into the numerator. This file keeps ``skipped`` verbatim
alongside ``passed`` and precomputes both readings, which is what lets EVAL-P0.4 freeze
``evaluated_cases`` (skipped excluded) as the canonical denominator.

The payload carries no timestamp: the artifact is committed, so git holds the date and
re-running an unchanged suite produces a byte-identical file that diffs cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

# Schema version of the emitted payload; bump on any breaking key change.
SCHEMA_VERSION: int = 1

# Expectation keys copied through to the artifact, in this order.
_EXPECTATION_KEYS: tuple[str, ...] = ("kind", "passed", "skipped", "detail")

_JSON_INDENT: int = 2


class DuplicateCaseIdError(Exception):
    """Raised when two results share a case_id.

    A dict keyed by case_id would silently drop the earlier verdict, quietly
    shrinking the denominator the whole baseline exists to pin down.
    """

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        super().__init__(
            f"Duplicate case_id {case_id!r} in eval results — verdicts must be unique "
            f"per case or the persisted denominator is wrong."
        )


def is_skipped(result: dict[str, Any]) -> bool:
    """True when a case has no expectations or every expectation was skipped.

    Args:
        result: A per-case result dict as built by runner._run_case.
    Returns:
        Whether the case contributed nothing to the evaluated denominator.
    """
    expectations = result.get("expectations", [])
    if not expectations:
        return True
    return all(exp.get("skipped") for exp in expectations)


def _expectation_entry(exp: dict[str, Any]) -> dict[str, Any]:
    """Project one expectation result onto the stable artifact schema."""
    return {
        "kind": exp.get("kind", ""),
        "passed": bool(exp.get("passed", False)),
        "skipped": bool(exp.get("skipped", False)),
        "detail": exp.get("detail", ""),
    }


def _case_entry(result: dict[str, Any]) -> dict[str, Any]:
    """Project one case result onto the stable artifact schema."""
    return {
        "passed": bool(result.get("passed", False)),
        "skipped": is_skipped(result),
        "description": result.get("description", ""),
        "expectations": [_expectation_entry(e) for e in result.get("expectations", [])],
    }


def build_payload(results: Sequence[dict[str, Any]], source: str) -> dict[str, Any]:
    """Build the verdicts payload for a completed run.

    Args:
        results: Per-case result dicts (runner._run_case / anti-hallucination shape).
        source: Which runner produced them, e.g. "runner" or "anti_hallucination".
    Returns:
        A JSON-serializable dict with schema_version, source, totals and cases.
    Raises:
        DuplicateCaseIdError: If two results share a case_id.
    """
    cases: dict[str, Any] = {}
    for result in results:
        case_id = str(result.get("case_id", ""))
        if case_id in cases:
            raise DuplicateCaseIdError(case_id)
        cases[case_id] = _case_entry(result)

    skipped = sum(1 for entry in cases.values() if entry["skipped"])
    passed_raw = sum(1 for entry in cases.values() if entry["passed"])
    passed_evaluated = sum(
        1 for entry in cases.values() if entry["passed"] and not entry["skipped"]
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "totals": {
            "total_cases": len(cases),
            "skipped_cases": skipped,
            "evaluated_cases": len(cases) - skipped,
            "passed_cases_raw": passed_raw,
            "passed_evaluated": passed_evaluated,
        },
        "cases": cases,
    }


def write_verdicts(
    results: Sequence[dict[str, Any]],
    path: Path,
    source: str = "runner",
) -> Path:
    """Write per-case verdicts to ``path`` as JSON, creating parent directories.

    Args:
        results: Per-case result dicts from a completed run.
        path: Destination file, e.g. evals/generations/baseline/verdicts.json.
        source: Which runner produced the results.
    Returns:
        The path written.
    Raises:
        DuplicateCaseIdError: If two results share a case_id.
        OSError: If the file cannot be written.
    """
    payload = build_payload(results, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=_JSON_INDENT, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
