"""
Module: check_test_quality
Layer: scripts (dev tooling)
Purpose: Static scan of tests/** flagging anti-vacuous-test patterns found in the
         2026-08-10 audit: bare Exception raises, self-referential sum assertions,
         vacuous mock-not-called checks, parametrized tests with no SUT calls,
         completely empty test bodies, tests that call the SUT but assert nothing
         (R1.8), existence-only assertions (hasattr, iscoroutinefunction), and
         constant-equals-literal assertions (T12.1 — Rule 5 gate).
         Ratchet-style gate: exits 1 when findings exceed the count recorded in
         check_test_quality_baseline.txt (tests/) or check_test_quality_demo_baseline.txt
         (demo_game/tests/). Both roots are scanned by default; pass --tests-dir to
         scan a single root (used by unit tests of this script).
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
EMPTY_TEST_BODY = "EMPTY_TEST_BODY"
NO_ASSERTION = "NO_ASSERTION"
EXISTENCE_ONLY_ASSERTION = "EXISTENCE_ONLY_ASSERTION"
CONSTANT_EQ_LITERAL = "CONSTANT_EQ_LITERAL"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TESTS_ROOT = _REPO_ROOT / "tests"
_DEMO_TESTS_ROOT = _REPO_ROOT / "demo_game" / "tests"
_BASELINE_PATH = Path(__file__).resolve().parent / "check_test_quality_baseline.txt"
_DEMO_BASELINE_PATH = Path(__file__).resolve().parent / "check_test_quality_demo_baseline.txt"

_EXISTENCE_ONLY_FUNCS: frozenset[str] = frozenset({"hasattr", "iscoroutinefunction"})


class Finding(BaseModel):
    """A flagged anti-vacuous-test pattern location."""

    model_config = ConfigDict(frozen=True)
    file: str
    test: str
    line: int
    pattern: str
    detail: str


_ASSERTION_CALL_NAMES: frozenset[str] = frozenset({"raises", "fail"})


def _has_assertion(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the test asserts something.

    Recognises the bare `assert` statement plus the call forms that stand in for it:
    `pytest.raises(...)`, `pytest.fail(...)`, and any `assert*` method such as
    `mock.assert_called_once_with` or `self.assertEqual`.

    Args:
        fn: The test function node to inspect.
    Returns:
        True when at least one assertion form is present anywhere in the function.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute)
            else ""
        )
        if name in _ASSERTION_CALL_NAMES or name.startswith("assert"):
            return True
    return False


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


def _patch_aliases(body: list[ast.stmt]) -> dict[str, str]:
    """Map alias_name → patch target source for 'with patch(...) as alias:' at body top level."""
    aliases: dict[str, str] = {}
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
                target = ce.args[0] if isinstance(ce, ast.Call) and ce.args else None
                aliases[item.optional_vars.id] = ast.unparse(target) if target else ""
    return aliases


def _is_alias_attr(node: ast.expr, alias: str, attr: str) -> bool:
    """True when node is the attribute access `alias.attr`."""
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == alias
        and node.attr == attr
    )


def _asserts_called(fn: ast.FunctionDef | ast.AsyncFunctionDef, alias: str) -> bool:
    """True when fn asserts the mock `alias` WAS called: assert_called*/assert_awaited*,
    `assert alias.called`, or `assert alias.call_count == N` with N non-zero."""
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == alias
            and node.func.attr.startswith(("assert_called", "assert_awaited", "assert_any_call"))
        ):
            return True
        if not isinstance(node, ast.Assert):
            continue
        t = node.test
        if _is_alias_attr(t, alias, "called"):
            return True
        if (
            isinstance(t, ast.Compare)
            and _is_alias_attr(t.left, alias, "call_count")
            and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value != 0
        ):
            return True
    return False


def _reachable_targets(tree: ast.AST) -> frozenset[str]:
    """Patch targets that some test in the file proves the SUT reaches.

    A not-called check on such a target is not vacuous: a sibling test shows the
    patched symbol sits on a real code path, so "not called" is a real claim.
    """
    return frozenset(
        target
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and fn.name.startswith("test_")
        for alias, target in _patch_aliases(fn.body).items()
        if target and _asserts_called(fn, alias)
    )


def _is_called_false(t: ast.expr, alias: str) -> bool:
    """True for `not alias.called` or `alias.called is False`."""
    if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
        return _is_alias_attr(t.operand, alias, "called")
    return (
        isinstance(t, ast.Compare)
        and _is_alias_attr(t.left, alias, "called")
        and isinstance(t.ops[0], ast.Is)
        and isinstance(t.comparators[0], ast.Constant)
        and t.comparators[0].value is False
    )


def _not_called_lineno(body: list[ast.stmt], alias: str) -> int | None:
    """Return lineno of a not-called check on alias: 'assert alias.call_count == 0',
    'alias.assert_not_called()', 'assert not alias.called' or 'assert alias.called is False'."""
    for stmt in body:
        if isinstance(stmt, ast.Assert):
            t = stmt.test
            if _is_called_false(t, alias):
                return stmt.lineno
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


def _is_existence_only_call(node: ast.expr) -> bool:
    """True when node calls an existence-only function (hasattr, iscoroutinefunction),
    bare or module-qualified (inspect.iscoroutinefunction)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
    return name in _EXISTENCE_ONLY_FUNCS


def _is_constant_eq_literal(assert_node: ast.Assert) -> bool:
    """True when assert compares a literal to a literal or to a bare module constant:
    `assert 1 == 1`, or `assert MAX_CHARS == 1000` (restates the source; T11.1c, rule 5)."""
    test = assert_node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
    ):
        return False
    sides = (test.left, test.comparators[0])
    return any(isinstance(x, ast.Constant) for x in sides) and all(
        isinstance(x, ast.Constant) or _is_module_constant(x) for x in sides
    )


def _is_module_constant(node: ast.expr) -> bool:
    """True for a bare UPPER_SNAKE name such as MAX_PLAYER_MESSAGE_CHARS."""
    return isinstance(node, ast.Name) and node.id.lstrip("_").isupper()


def _scan_fn(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    reachable: frozenset[str],
    relpath: str,
) -> list[Finding]:
    """Scan a single test function for every anti-vacuous pattern."""
    findings: list[Finding] = []
    name = fn.name

    # Pattern 1: bare Exception raises
    for node in ast.walk(fn):
        if isinstance(node, ast.With):
            ln = _is_raises_exception(node)
            if ln:
                findings.append(Finding(
                    file=relpath, test=name, line=ln,
                    pattern=BARE_EXCEPTION_RAISES,
                    detail="pytest.raises(Exception) — use a specific exception type",
                ))

    # Pattern 2: self-referential sum assertion
    for stmt in fn.body:
        if isinstance(stmt, ast.Assert) and isinstance(stmt.test, ast.Compare):
            if _is_self_referential(stmt.test):
                findings.append(Finding(
                    file=relpath, test=name, line=stmt.lineno,
                    pattern=SELF_REFERENTIAL_SUM,
                    detail="sum-of-parts == total where total is derived from the same parts",
                ))

    # Pattern 3: patch() + assert mock not called
    for alias, target in _patch_aliases(fn.body).items():
        ln = _not_called_lineno(fn.body, alias)
        if ln and target not in reachable:
            findings.append(Finding(
                file=relpath, test=name, line=ln,
                pattern=VACUOUS_MOCK_NOT_CALLED,
                detail=(
                    f"assert {alias}.call_count == 0 — "
                    "no test in this file asserts the patched symbol IS called"
                ),
            ))

    # Pattern 4: parametrized test with no function calls in body
    has_parametrize = any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr == "parametrize"
        for d in fn.decorator_list
    )
    if has_parametrize:
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

    # Pattern 7: existence-only assertion (hasattr, iscoroutinefunction)
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert) and _is_existence_only_call(node.test):
            func_name = ast.unparse(node.test.func)  # type: ignore[attr-defined]
            findings.append(Finding(
                file=relpath, test=name, line=node.lineno,
                pattern=EXISTENCE_ONLY_ASSERTION,
                detail=(
                    f"assert {func_name}(...) only checks existence — "
                    "assert the actual value instead"
                ),
            ))

    # Pattern 8: constant-equals-literal (assert 1 == 1, assert MAX_CHARS == 1000)
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert) and _is_constant_eq_literal(node):
            findings.append(Finding(
                file=relpath, test=name, line=node.lineno,
                pattern=CONSTANT_EQ_LITERAL,
                detail=(
                    "assert <literal or MODULE_CONSTANT> == <literal> — "
                    "restates the source; assert a computed value"
                ),
            ))

    # Patterns 5 and 6: the test asserts nothing, so it can only fail by raising.
    # The two partition on whether the body does anything at all, so a test is
    # reported once, never twice.
    if not _has_assertion(fn):
        body_has_call = any(
            isinstance(node, ast.Call)
            for stmt in fn.body
            for node in ast.walk(stmt)
        )
        findings.append(Finding(
            file=relpath, test=name, line=fn.lineno,
            pattern=NO_ASSERTION if body_has_call else EMPTY_TEST_BODY,
            detail=(
                "test calls the SUT but asserts nothing — it can only fail by raising"
                if body_has_call
                else "test body contains no assertions and no function calls"
            ),
        ))

    return findings


def scan_file(path: Path) -> list[Finding]:
    """Parse a test file and return all anti-vacuous findings."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    reachable = _reachable_targets(tree)
    relpath = str(path)
    return [
        finding
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for finding in _scan_fn(node, reachable, relpath)
    ]


def scan_directory(root: Path) -> list[Finding]:
    """Scan all test_*.py files under root recursively."""
    if not root.exists():
        return []
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
    out.append("Each item must be fixed; the '# quality-ok:' waiver is removed (T12.1, Rule 5).")
    return "\n".join(out)


def _read_baseline(path: Path) -> int:
    """Return the recorded baseline count; 0 if the file does not exist or is unreadable."""
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return 0


def _check_one(tests_dir: Path, baseline_file: Path, label: str) -> int:
    """Scan one test tree, print findings, and return 1 if count exceeds baseline.

    Args:
        tests_dir: Root of the test tree to scan.
        baseline_file: Path to the baseline count file (single integer).
        label: Short label for display (empty string for the main tree).
    Returns:
        0 when findings are within baseline, 1 when they exceed it.
    """
    findings = scan_directory(tests_dir)
    prefix = f"[{label}] " if label else ""
    print(format_findings(findings).replace("check-test-quality:", f"{prefix}check-test-quality:"))
    baseline = _read_baseline(baseline_file)
    count = len(findings)
    if count > baseline:
        print(
            f"{prefix}check-test-quality: {count} finding(s) exceed baseline of {baseline} — gate RED.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Scan tests for anti-vacuous patterns. Exits 1 above baseline (R1.2, T12.1)."""
    parser = argparse.ArgumentParser(
        description="Anti-vacuous test quality scan. Ratchet-style: exits 1 above baseline."
    )
    parser.add_argument(
        "--tests-dir", type=Path, default=None,
        help="Root of a single test tree to scan (overrides default dual-root scan).",
    )
    parser.add_argument(
        "--baseline-file", type=Path, default=None,
        help="Path to the baseline count file (single integer).",
    )
    args = parser.parse_args(argv)

    if args.tests_dir is not None:
        baseline_file = args.baseline_file or _BASELINE_PATH
        return _check_one(args.tests_dir, baseline_file, "")

    exit_main = _check_one(_TESTS_ROOT, _BASELINE_PATH, "")
    exit_demo = _check_one(_DEMO_TESTS_ROOT, _DEMO_BASELINE_PATH, "demo_game/tests")
    return max(exit_main, exit_demo)


if __name__ == "__main__":
    sys.exit(main())
