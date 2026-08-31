#!/usr/bin/env python
"""
Module: check_engine_logs
Layer: scripts (dev tooling)
Purpose: Fail when engine logger.info calls omit duration_ms, the field CLAUDE.md
         requires on every engine log entry. Ratchet-style: 42 of the 59 logger.info
         calls in engines/ were non-compliant when this gate landed (R1.8), so that
         count is the recorded baseline and any increase is RED. Fixing sites lowers
         the count; re-record with --update.
Counterfactual: add a logger.info("event", extra={"npc_id": "x"}) to any engine file
         without duration_ms and the count exceeds baseline — gate RED.
Dependencies: argparse, ast, pathlib, sys, pydantic
Used by: make check-engine-logs, tests/unit/scripts/test_check_engine_logs.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

ENGINES_DIR = Path(__file__).resolve().parents[1] / "src" / "npc_engine" / "engines"
REQUIRED_LOG_FIELD = "duration_ms"
BASELINE_PATH = Path(__file__).resolve().parent / "engine_logs_baseline.txt"
_LOGGER_NAMES: frozenset[str] = frozenset({"logger", "_logger", "log"})


class LogFinding(BaseModel):
    """A logger.info call in engines/ that is missing the required extra field."""

    model_config = ConfigDict(frozen=True)
    file: str
    line: int
    missing_field: str


def _extra_keys(call_node: ast.Call) -> set[str]:
    """Extract string keys from the extra={...} kwarg of a logger call."""
    for kw in call_node.keywords:
        if kw.arg != "extra":
            continue
        if isinstance(kw.value, ast.Dict):
            return {
                k.value
                for k in kw.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
    return set()


def _is_logger_info(node: ast.Call) -> bool:
    """True if the call is <logger_name>.info(...)."""
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "info":
        return False
    return isinstance(func.value, ast.Name) and func.value.id in _LOGGER_NAMES


def scan_file(path: Path) -> list[LogFinding]:
    """Return LogFinding entries for logger.info calls missing required fields."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    findings: list[LogFinding] = []
    relpath = str(path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_logger_info(node):
            continue
        if REQUIRED_LOG_FIELD not in _extra_keys(node):
            findings.append(LogFinding(
                file=relpath, line=node.lineno, missing_field=REQUIRED_LOG_FIELD,
            ))
    return findings


def scan_engines(root: Path) -> list[LogFinding]:
    """Scan all .py files under root for logger.info calls missing required fields."""
    findings: list[LogFinding] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        findings.extend(scan_file(path))
    return findings


def _report(findings: list[LogFinding]) -> str:
    """Format findings as a human-readable string."""
    if not findings:
        return f"check-engine-logs: OK — all logger.info calls include '{REQUIRED_LOG_FIELD}'.\n"
    lines = [
        f"check-engine-logs: {len(findings)} logger.info call(s) missing '{REQUIRED_LOG_FIELD}':",
    ]
    for f in findings[:20]:
        lines.append(f"  {f.file}:{f.line}  missing: {f.missing_field}")
    if len(findings) > 20:
        lines.append(f"  ... and {len(findings) - 20} more.")
    lines.append(f"Each engine log entry must include {REQUIRED_LOG_FIELD} in extra={{}}.")
    return "\n".join(lines)


def _read_baseline(path: Path) -> int:
    """Return the recorded baseline count; 0 when the file is missing or unreadable."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Fail when engine logger.info calls missing duration_ms exceed the baseline."""
    parser = argparse.ArgumentParser(description="Engine log field gate (ratchet).")
    parser.add_argument("--update", action="store_true", help="Record the current count.")
    parser.add_argument("--engines-dir", type=Path, default=ENGINES_DIR)
    parser.add_argument("--baseline-file", type=Path, default=BASELINE_PATH)
    args = parser.parse_args(argv)

    findings = scan_engines(args.engines_dir)
    count = len(findings)
    if args.update:
        args.baseline_file.write_text(f"{count}\n", encoding="utf-8", newline="")
        print(f"check-engine-logs: baseline recorded at {count}")
        return 0

    print(_report(findings))
    baseline = _read_baseline(args.baseline_file)
    if count > baseline:
        print(
            f"check-engine-logs: {count} finding(s) exceed baseline of {baseline} — gate RED.",
            file=sys.stderr,
        )
        return 1
    if count < baseline:
        print(f"check-engine-logs: {count} < baseline {baseline} — re-record with --update.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
