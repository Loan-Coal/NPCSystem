"""
Module: check_conservation
Layer: scripts (dev tooling)
Purpose: Verify each aggregator's output accounts for its whole input. Exits 0 always
         (report-only) until EVAL-P17.6 wires it as a gate. Identity 4 is DEFERRED to
         EVAL-P17.4 — it spans two different artifact producers and comparing them as-is
         creates a definitional mismatch, not a real conservation violation.
Dependencies: argparse, json, pathlib, sys, pydantic; evals/case_stats (classify_battery)
Used by: make check-conservation, tests/unit/scripts/test_check_conservation.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from case_stats import classify_battery  # noqa: E402

_OUTPUTS_FILE = "outputs.jsonl"
_JUDGED_FILE = "judged.jsonl"
_DET_JUDGED_FILE = "deterministic_judged.jsonl"
_DEFAULT_GEN_DIR = (
    Path(__file__).resolve().parents[1] / "evals" / "generations" / "k3_73e6c36"
)


class Identity1Report(BaseModel):
    """Battery coverage: guard + capability + excluded == total cases."""

    model_config = ConfigDict(frozen=True)
    ok: bool
    total_cases: int
    guard_cases: int
    capability_cases: int
    explicitly_excluded_cases: int
    neither_cases: int


class Identity2Report(BaseModel):
    """Compare slot coverage: slots_read_by_compare == |judged ∪ deterministic_judged|."""

    model_config = ConfigDict(frozen=True)
    ok: bool
    compare_slots: int
    all_slots: int
    compare_rows: int
    all_rows: int
    pct_unread: float


class Identity3Report(BaseModel):
    """Capability battery completeness: cap in judged == cap in outputs."""

    model_config = ConfigDict(frozen=True)
    ok: bool
    cap_in_judged: int
    cap_ran: int


class ConservationReport(BaseModel):
    """Full conservation audit over one generation artifact."""

    model_config = ConfigDict(frozen=True)
    gen_dir: str
    identity_1: Identity1Report
    identity_2: Identity2Report
    identity_3: Identity3Report


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file, skipping blank lines."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _extract_case_id(record_id: str) -> str:
    """Extract case_id from record_id (format: case_id:matcher_kind:repetition)."""
    parts = record_id.rsplit(":", 2)
    return parts[0] if len(parts) == 3 else record_id


def _battery(case_id: str) -> str | None:
    """Return battery name or None when case_id matches no battery prefix."""
    try:
        return classify_battery(case_id)
    except ValueError:
        return None


def _check_identity_1(outputs: list[dict[str, Any]]) -> Identity1Report:
    """Identity 1: guard + capability + excluded == total cases.

    Args:
        outputs: Rows from outputs.jsonl.
    Returns:
        Identity1Report with per-battery breakdown and ok flag.
    """
    case_ids = {_extract_case_id(r["record_id"]) for r in outputs}
    total = len(case_ids)
    guard = capability = neither = 0
    for cid in case_ids:
        b = _battery(cid)
        if b == "guard":
            guard += 1
        elif b == "capability":
            capability += 1
        else:
            neither += 1
    excluded = 0
    return Identity1Report(
        ok=(guard + capability + excluded == total),
        total_cases=total,
        guard_cases=guard,
        capability_cases=capability,
        explicitly_excluded_cases=excluded,
        neither_cases=neither,
    )


def _check_identity_2(gen_dir: Path) -> Identity2Report:
    """Identity 2: compare slot coverage.

    `compare` reads only judged.jsonl; deterministic_judged.jsonl is not joined.

    Args:
        gen_dir: Generation directory containing the verdict files.
    Returns:
        Identity2Report with slot counts and ok flag.
    """
    judged_path = gen_dir / _JUDGED_FILE
    det_path = gen_dir / _DET_JUDGED_FILE
    judged_rows: list[dict[str, Any]] = _load_jsonl(judged_path) if judged_path.exists() else []
    det_rows: list[dict[str, Any]] = _load_jsonl(det_path) if det_path.exists() else []
    judged_rids = {r["record_id"] for r in judged_rows}
    det_rids = {r["record_id"] for r in det_rows}
    compare_slots = len(judged_rids)
    all_slots = len(judged_rids | det_rids)
    all_rows = len(judged_rows) + len(det_rows)
    pct_unread = round((1 - compare_slots / all_slots) * 100, 1) if all_slots else 0.0
    return Identity2Report(
        ok=(compare_slots == all_slots),
        compare_slots=compare_slots,
        all_slots=all_slots,
        compare_rows=len(judged_rows),
        all_rows=all_rows,
        pct_unread=pct_unread,
    )


def _check_identity_3(outputs: list[dict[str, Any]], gen_dir: Path) -> Identity3Report:
    """Identity 3: capability cases in judged == capability cases in outputs.

    Args:
        outputs: Rows from outputs.jsonl.
        gen_dir: Generation directory containing judged.jsonl.
    Returns:
        Identity3Report with capability counts and ok flag.
    """
    cap_ran = {
        _extract_case_id(r["record_id"])
        for r in outputs
        if _battery(_extract_case_id(r["record_id"])) == "capability"
    }
    judged_path = gen_dir / _JUDGED_FILE
    cap_in_judged: set[str] = set()
    if judged_path.exists():
        for row in _load_jsonl(judged_path):
            cid = row.get("case_id") or _extract_case_id(row["record_id"])
            if _battery(cid) == "capability":
                cap_in_judged.add(cid)
    return Identity3Report(
        ok=(cap_in_judged == cap_ran),
        cap_in_judged=len(cap_in_judged),
        cap_ran=len(cap_ran),
    )


def check_conservation(gen_dir: Path) -> ConservationReport:
    """Run all conservation identity checks against a generation directory.

    Args:
        gen_dir: Path to the generation directory (must contain outputs.jsonl).
    Returns:
        ConservationReport with results for identities 1-3.
    """
    outputs = _load_jsonl(gen_dir / _OUTPUTS_FILE)
    return ConservationReport(
        gen_dir=str(gen_dir),
        identity_1=_check_identity_1(outputs),
        identity_2=_check_identity_2(gen_dir),
        identity_3=_check_identity_3(outputs, gen_dir),
    )


def format_report(report: ConservationReport) -> str:
    """Format a ConservationReport as a human-readable string.

    Args:
        report: Conservation audit result.
    Returns:
        Multi-line report string.
    """
    lines = [f"Conservation audit: {report.gen_dir}", ""]
    r1 = report.identity_1
    s1 = "OK" if r1.ok else "FAIL"
    d1 = (
        f"{r1.guard_cases} guard + {r1.capability_cases} capability = "
        f"{r1.guard_cases + r1.capability_cases} of {r1.total_cases} cases; "
        f"{r1.neither_cases} cases in no battery"
        if not r1.ok
        else f"{r1.guard_cases} guard + {r1.capability_cases} capability = {r1.total_cases} OK"
    )
    lines.append(f"  Identity 1 [{s1}]: guard_cases + capability_cases == total_cases")
    lines.append(f"    {d1}")

    r2 = report.identity_2
    s2 = "OK" if r2.ok else "FAIL"
    d2 = (
        f"compare reads {r2.compare_slots} of {r2.all_slots} unique record_ids "
        f"({r2.compare_rows} of {r2.all_rows} rows with repetitions) — "
        f"{r2.pct_unread}% never read"
        if not r2.ok
        else f"compare reads all {r2.compare_slots} unique record_ids OK"
    )
    lines.append(f"  Identity 2 [{s2}]: slots_read_by_compare == |judged ∪ deterministic_judged|")
    lines.append(f"    {d2}")

    r3 = report.identity_3
    s3 = "OK" if r3.ok else "FAIL"
    d3 = (
        f"capability battery sees {r3.cap_in_judged}, while {r3.cap_ran} capability cases ran"
        if not r3.ok
        else f"capability battery sees all {r3.cap_ran} capability cases OK"
    )
    lines.append(f"  Identity 3 [{s3}]: capability_battery_cases == capability_cases_actually_run")
    lines.append(f"    {d3}")
    lines.append("")
    lines.append(
        "  Identity 4 [DEFERRED to EVAL-P17.4]: sum(battery case counts) == unique cases in outputs"
    )
    lines.append(
        "    Deferred: right-hand side measures a different population from a live eval run."
    )
    lines.append("")
    failed = sum(1 for r in [report.identity_1, report.identity_2, report.identity_3] if not r.ok)
    lines.append(
        f"{failed} violation(s) found (report-only until EVAL-P17.6)."
        if failed
        else "All identities satisfied."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse args, run audit, print report, exit 0 (report-only until EVAL-P17.6).

    Args:
        argv: Argument list (defaults to sys.argv[1:]).
    Returns:
        Always 0.
    """
    parser = argparse.ArgumentParser(
        description="Conservation audit — reports violations, exits 0 until EVAL-P17.6."
    )
    parser.add_argument(
        "--gen-dir",
        type=Path,
        default=_DEFAULT_GEN_DIR,
        help="Generation directory to audit (default: evals/generations/k3_73e6c36)",
    )
    args = parser.parse_args(argv)
    print(format_report(check_conservation(args.gen_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
