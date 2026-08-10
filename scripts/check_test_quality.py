"""
Module: check_test_quality
Layer: scripts (dev tooling)
Purpose: Static scan of tests/** flagging anti-vacuous-test patterns found in the
         2026-08-10 audit: bare Exception raises, self-referential sum assertions,
         vacuous mock-not-called checks, and parametrized tests with no SUT calls.
         Exits 0 always (report-only); gate wired into make check in EVAL-P15.4.
         Each flagged item must be fixed or inline-suppressed with '# quality-ok: <reason>'.
Dependencies: argparse, ast, pathlib, sys, pydantic
Used by: make check-test-quality, tests/unit/scripts/test_check_test_quality.py
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, ConfigDict

BARE_EXCEPTION_RAISES = "BARE_EXCEPTION_RAISES"
SELF_REFERENTIAL_SUM = "SELF_REFERENTIAL_SUM"
VACUOUS_MOCK_NOT_CALLED = "VACUOUS_MOCK_NOT_CALLED"
PARAMETRIZE_NO_SUT_CALL = "PARAMETRIZE_NO_SUT_CALL"

_WAIVER_MARKER = "# quality-ok:"
_TESTS_ROOT = Path(__file__).resolve().parents[1] / "tests"


class Finding(BaseModel):
    """A flagged anti-vacuous-test pattern location."""

    model_config = ConfigDict(frozen=True)
    file: str
    test: str
    line: int
    pattern: str
    detail: str


def _is_waived(lines: list[str], lineno: int) -> bool:
    """True if the source line or preceding line contains the quality-ok marker."""
    idx = lineno - 1
    if idx < len(lines) and _WAIVER_MARKER in lines[idx]:
        return True
    return idx > 0 and _WAIVER_MARKER in lines[idx - 1]


def _collect_attr_roots(node: ast.expr) -> set[str]:
    """Collect root variable names from a BinOp(Add) chain over attribute accesses."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return {node.value.id}
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _collect_attr_roots(node.left) | _collect_attr_roots(node.right)
    return set()


def _is_self_referential(cmp: ast.Compare) -> bool:
    """True for 'a.x + a.y + ... == a.total' where all attrs share one root name."""
    if len(cmp.ops) != 1 or not isinstance(cmp.ops[0], ast.Eq):
        return False
    if len(cmp.comparators) != 1 or not isinstance(cmp.left, ast.BinOp):
        return False
    comp = cmp.comparators[0]
    if not isinstance(comp, ast.Attribute) or not isinstance(comp.value, ast.Name):
        return False
    roots = _collect_attr_roots(cmp.left)
    return len(roots) == 1 and comp.value.id in roots


def _is_raises_exception(with_node: ast.With) -> int | None:
    """Return lineno if with_node is 'with pytest.raises(Exception):', else None."""
    for item in with_node.items:
        expr = item.context_expr
        if not isinstance(expr, ast.Call):
            continue
        func = expr.func
        is_raises = (isinstance(func, ast.Name) and func.id == "raises") or (
            isinstance(func, ast.Attribute) and func.attr == "raises"
        )
        if (
            is_raises
            and expr.args
            and isinstance(expr.args[0], ast.Name)
            and expr.args[0].id == "Exception"
        ):
            return with_node.lineno
    return None


def _patch_aliases(body: list[ast.stmt]) -> dict[str, int]:
    """Map alias_name → lineno for 'with patch(...) as alias:' at body top level."""
    aliases: dict[str, int] = {}
    for stmt in body:
        if not isinstance(stmt, ast.With):
            continue
        for item in stmt.items:
            ce = item.context_expr
            is_patch = isinstance(ce, ast.Call) and (
                (isinstance(ce.func, ast.Name) and ce.func.id == "patch")
                or (isinstance(ce.func, ast.Attribute) and ce.func.attr == "patch")
            )
            if is_patch and isinstance(item.optional_vars, ast.Name):
                aliases[item.optional_vars.id] = stmt.lineno
    return aliases


def _not_called_lineno(body: list[ast.stmt], alias: str) -> int | None:
    """Return lineno of 'assert alias.call_count==0' or 'alias.assert_not_called()' if found."""
    for stmt in body:
        if isinstance(stmt, ast.Assert):
            t = stmt.test
            if (
                isinstance(t, ast.Compare)
                and isinstance(t.left, ast.Attribute)
                and isinstance(t.left.value, ast.Name)
                and t.left.value.id == alias
                and t.left.attr == "call_count"
                and len(t.ops) == 1
                and isinstance(t.ops[0], ast.Eq)
                and len(t.comparators) == 1
                and isinstance(t.comparators[0], ast.Constant)
                and t.comparators[0].value == 0
            ):
                return stmt.lineno
        if (
            isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == alias
            and stmt.value.func.attr == "assert_not_called"
        ):
            return stmt.lineno
    return None


def _scan_fn(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: list[str],
    relpath: str,
) -> list[Finding]:
    """Scan a single test function for all four anti-vacuous patterns."""
    findings: list[Finding] = []
    name = fn.name

    # Pattern 1: bare Exception raises
    for node in ast.walk(fn):
        if isinstance(node, ast.With):
            ln = _is_raises_exception(node)
            if ln and not _is_waived(lines, ln):
                findings.append(Finding(
                    file=relpath, test=name, line=ln,
                    pattern=BARE_EXCEPTION_RAISES,
                    detail="pytest.raises(Exception) — use a specific exception type",
                ))

    # Pattern 2: self-referential sum assertion
    for stmt in fn.body:
        if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Compare):
            if _is_self_referential(stmt.test) and not _is_waived(lines, stmt.lineno):
                findings.append(Finding(
                    file=relpath, test=name, line=stmt.lineno,
                    pattern=SELF_REFERENTIAL_SUM,
                    detail="sum-of-parts == total where total is derived from the same parts",
                ))

    # Pattern 3: patch() + assert mock not called
    for alias in _patch_aliases(fn.body):
        ln = _not_called_lineno(fn.body, alias)
        if ln and not _is_waived(lines, ln):
            findings.append(Finding(
                file=relpath, test=name, line=ln,
                pattern=VACUOUS_MOCK_NOT_CALLED,
                detail=(
                    f"assert {alias}.call_count == 0 — "
                    "verify the patched symbol is reachable by the SUT"
                ),
            ))

    # Pattern 4: parametrized test with no function calls in body
    has_parametrize = any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr == "parametrize"
        for d in fn.decorator_list
    )
    if has_parametrize and not _is_waived(lines, fn.lineno):
        has_calls = any(
            isinstance(node, ast.Call)
            for stmt in fn.body
            for node in ast.walk(stmt)
        )
        if not has_calls:
            findings.append(Finding(
                file=relpath, test=name, line=fn.lineno,
                pattern=PARAMETRIZE_NO_SUT_CALL,
                detail="@pytest.mark.parametrize test makes no function calls in its body",
            ))

    return findings


def scan_file(path: Path) -> list[Finding]:
    """Parse a test file and return all unwaived anti-vacuous findings."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    lines = source.splitlines()
    relpath = str(path)
    return [
        finding
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for finding in _scan_fn(node, lines, relpath)
    ]


def scan_directory(root: Path) -> list[Finding]:
    """Scan all test_*.py files under root recursively."""
    findings: list[Finding] = []
    for path in sorted(root.rglob("test_*.py")):
        findings.extend(scan_file(path))
    return findings


def format_findings(findings: list[Finding]) -> str:
    """Return a human-readable summary of findings grouped by pattern."""
    if not findings:
        return "check-test-quality: 0 issues found.\n"
    by_pattern: dict[str, list[Finding]] = {}
    for f in findings:
        by_pattern.setdefault(f.pattern, []).append(f)
    out: list[str] = [f"check-test-quality: {len(findings)} issue(s) found\n"]
    for pattern, items in sorted(by_pattern.items()):
        out.append(f"  {pattern} ({len(items)}):")
        for item in items:
            out.append(f"    {item.file}::{item.test}:{item.line}  {item.detail}")
        out.append("")
    out.append("Each item must be fixed or suppressed with '# quality-ok: <reason>'.")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    """Scan tests for anti-vacuous patterns. Exits 0 always (report-only until EVAL-P15.4)."""
    parser = argparse.ArgumentParser(
        description="Anti-vacuous test quality scan (report-only; gate wired in EVAL-P15.4)."
    )
    parser.add_argument(
        "--tests-dir", type=Path, default=_TESTS_ROOT,
        help="Root of the test tree to scan.",
    )
    args = parser.parse_args(argv)
    findings = scan_directory(args.tests_dir)
    print(format_findings(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
