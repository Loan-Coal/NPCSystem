#!/usr/bin/env python
"""
Module: check_rules
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Enforce the strict CLAUDE.md code rules as an executable, ratcheted gate.
Dependencies: stdlib only.
Used by: `make check-rules`, `make check-evals-rules`, pre-commit, CI static-analysis.

This scanner turns the prose rules in project-harness/CLAUDE.md into checks. It uses
a *baseline ratchet*: existing (grandfathered) violations are recorded in
scripts/rules_baseline.txt; the gate fails only when a NEW violation appears. Fixing
a baselined violation is reported and can be persisted with --update-baseline, so the
debt can only ever shrink - it can never silently grow.

evals/ is checked separately (--evals flag) against scripts/evals_baseline.txt using
the same ratchet pattern.

Rules:
  R001 file-size   - non-test .py over 800 lines (DEC-226 hard unwaivable gate);
                     files 401-800 lines emit a soft advisory only (no gate, no waiver).
                     Grandfathered R001 entries record line count; growing past that count
                     is a new violation regardless of absolute size.
  R002 print       - print() in src/npc_engine and evals/ (CLAUDE.md "never print(), use logging")
  R003 swallow     - `except ...: pass` (CLAUDE.md "never swallow errors")
  R004 raise-exc   - `raise Exception(` (CLAUDE.md "custom exception hierarchy only")
  R005 cypher-leak - Cypher / session.run / begin_transaction outside graph/ (layer rule)
  R006 fn-length   - function/method over 40 lines (CLAUDE.md "no function exceeds 40 lines")
  R007 demo-import - demo_game importing npc_engine (zero-src-import contract)

Signatures for R001 are line-count-bearing ("R001|relative/path:NNNN") so the gate
catches files that grow beyond their grandfathered size. All other rules use file- or
function-level signatures ("RULE|relative/path" or "RULE|path::name") that are stable
across edits unrelated to the violation.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "rules_baseline.txt"
EVALS_BASELINE_PATH = Path(__file__).resolve().parent / "evals_baseline.txt"

SOFT_LINE_LIMIT = 400   # DEC-226: advisory only — no gate, no waiver list
HARD_LINE_LIMIT = 800   # DEC-226: hard unwaivable gate
MAX_FUNCTION_LINES = 40  # CLAUDE.md: "no function or method may exceed 40 lines"

# Cypher / transaction patterns that must live in graph/ only.
_CYPHER_RE = re.compile(r"\b(?:MATCH|MERGE|CREATE)\s*\(|session\.run\(|tx\.run\(|begin_transaction\(")
# `except ...: pass` on the same line OR a bare-body `pass` on the next line.
_SWALLOW_RE = re.compile(r"except[^\n:]*:\s*(?:#[^\n]*)?\n\s*pass\b|except[^\n:]*:\s*pass\b")
_RAISE_EXC_RE = re.compile(r"raise\s+Exception\(")
_PRINT_RE = re.compile(r"(?<![\w.])print\(")
_DEMO_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+npc_engine\b", re.MULTILINE)

# Cypher leak is checked in these src/npc_engine subpackages (everything but graph/).
_CYPHER_SCAN_DIRS = ("engines", "world", "retrieval", "services", "scheduler")


def _is_test_path(path: Path) -> bool:
    """True for test files/dirs, which are exempt from size and print rules."""
    parts = {p.lower() for p in path.parts}
    return "tests" in parts or path.name.startswith("test_") or path.name.endswith("_test.py")


def _read(path: Path) -> str:
    """Read a file as UTF-8, ignoring undecodable bytes."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _rel(path: Path) -> str:
    """Repo-relative POSIX path for stable signatures across OSes."""
    return path.relative_to(REPO_ROOT).as_posix()


def _iter_py(root: Path) -> list[Path]:
    """All .py files under a repo subdir (empty list if the dir is absent)."""
    base = REPO_ROOT / root
    return sorted(base.rglob("*.py")) if base.exists() else []


def _oversized_functions(text: str, rel: str) -> set[str]:
    """Return R006 signatures for functions/methods exceeding MAX_FUNCTION_LINES.

    Signature is `R006|path::Qualified.name` (no line numbers) so it stays stable
    across edits that keep the function over-limit; a newly oversized function
    produces a new signature the ratchet will flag.
    """
    out: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = (child.end_lineno or child.lineno) - child.lineno + 1
                qual = f"{prefix}{child.name}"
                if span > MAX_FUNCTION_LINES:
                    out.add(f"R006|{rel}::{qual}")
                walk(child, f"{qual}.")
            elif isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return out


def _file_violations(path: Path, rel: str) -> tuple[str | None, str | None]:
    """Return (gate_sig, advisory_sig) for a non-test file's line count.

    gate_sig is set when the file exceeds HARD_LINE_LIMIT.
    advisory_sig is set when the file is in the SOFT_LINE_LIMIT..HARD_LINE_LIMIT band.
    """
    nlines = len(_read(path).splitlines())
    if nlines > HARD_LINE_LIMIT:
        return f"R001|{rel}:{nlines}", None
    if nlines > SOFT_LINE_LIMIT:
        return None, f"R001-SOFT|{rel}:{nlines}"
    return None, None


def _parse_r001(sig: str) -> tuple[str, int | None]:
    """Parse R001|path or R001|path:N → (path, count_or_None).

    Args:
        sig: An R001 signature string.
    Returns:
        Tuple of (posix path, line count or None for legacy entries without count).
    """
    _, rest = sig.split("|", 1)
    if ":" in rest:
        path, cnt_str = rest.rsplit(":", 1)
        try:
            return path, int(cnt_str)
        except ValueError:
            return rest, None
    return rest, None


def _compare_r001(current: set[str], baseline: set[str]) -> tuple[set[str], set[str]]:
    """Compare R001 violations with line-count awareness (DEC-226).

    A grandfathered entry R001|path:M is still satisfied when the file's current
    count N ≤ M. Growing beyond M (N > M) is a new violation even if N ≤ HARD_LINE_LIMIT.
    A file that drops below HARD_LINE_LIMIT is considered resolved.

    Args:
        current: R001 signatures from _collect() (line-count-bearing).
        baseline: R001 signatures from the baseline file (may include legacy no-count entries).
    Returns:
        (new_violations, resolved_violations) as signature string sets.
    """
    baseline_map = {_parse_r001(s)[0]: _parse_r001(s)[1] for s in baseline}
    current_map = {_parse_r001(s)[0]: _parse_r001(s)[1] for s in current}

    new: set[str] = set()
    resolved: set[str] = set()

    for path, count in current_map.items():
        if path not in baseline_map:
            new.add(f"R001|{path}:{count}")
        elif baseline_map[path] is not None and count > baseline_map[path]:
            new.add(f"R001|{path}:{count}")
        # else: count <= grandfathered count — still within allowance, not new

    for path, b_count in baseline_map.items():
        if path not in current_map:
            suffix = f":{b_count}" if b_count is not None else ""
            resolved.add(f"R001|{path}{suffix}")

    return new, resolved


def _collect() -> tuple[set[str], set[str]]:
    """Scan src/ and demo_game/ and return (violations, advisories).

    violations: gate-blocking rule-violation signatures.
    advisories: R001-SOFT signatures for files in the SOFT_LINE_LIMIT..HARD_LINE_LIMIT band.
    """
    found: set[str] = set()
    advisories: set[str] = set()
    src = _iter_py("src/npc_engine")
    demo = _iter_py("demo_game")

    for path in src + demo:
        rel = _rel(path)
        if not _is_test_path(path):
            gate_sig, advisory_sig = _file_violations(path, rel)
            if gate_sig:
                found.add(gate_sig)
            if advisory_sig:
                advisories.add(advisory_sig)

    for path in src:
        if _is_test_path(path):
            continue
        text = _read(path)
        rel = _rel(path)
        found |= _oversized_functions(text, rel)
        if _PRINT_RE.search(text):
            found.add(f"R002|{rel}")
        if _SWALLOW_RE.search(text):
            found.add(f"R003|{rel}")
        if _RAISE_EXC_RE.search(text):
            found.add(f"R004|{rel}")
        if any(seg in path.parts for seg in _CYPHER_SCAN_DIRS) and _CYPHER_RE.search(text):
            found.add(f"R005|{rel}")

    for path in demo:
        if _DEMO_IMPORT_RE.search(_read(path)):
            found.add(f"R007|{_rel(path)}")
    return found, advisories


def _collect_evals() -> tuple[set[str], set[str]]:
    """Scan evals/ for rule violations (R001, R002, R003, R004, R006).

    Returns:
        (violations, advisories) in the same format as _collect().
    """
    found: set[str] = set()
    advisories: set[str] = set()
    for path in _iter_py("evals"):
        if _is_test_path(path):
            continue
        rel = _rel(path)
        text = _read(path)
        gate_sig, advisory_sig = _file_violations(path, rel)
        if gate_sig:
            found.add(gate_sig)
        if advisory_sig:
            advisories.add(advisory_sig)
        found |= _oversized_functions(text, rel)
        if _PRINT_RE.search(text):
            found.add(f"R002|{rel}")
        if _SWALLOW_RE.search(text):
            found.add(f"R003|{rel}")
        if _RAISE_EXC_RE.search(text):
            found.add(f"R004|{rel}")
    return found, advisories


def _load_baseline(path: Path = BASELINE_PATH) -> set[str]:
    """Load grandfathered signatures from the baseline file (comments allowed)."""
    if not path.exists():
        return set()
    lines = _read(path).splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def _write_baseline(signatures: set[str], path: Path = BASELINE_PATH) -> None:
    """Persist the baseline, sorted, with a header."""
    header = (
        "# Grandfathered CLAUDE.md rule violations - see scripts/check_rules.py.\n"
        "# The gate fails only on NEW violations. Shrink this file as debt is fixed\n"
        "# (run the corresponding update target). Never add a line by hand to dodge the gate.\n"
    )
    path.write_text(header + "\n".join(sorted(signatures)) + "\n", encoding="utf-8")


_RULE_HELP = {
    "R001": (
        f"file exceeds {HARD_LINE_LIMIT} non-test lines (hard unwaivable gate per DEC-226; "
        f"no DECISIONS.md waiver available — split the file). "
        f"Files {SOFT_LINE_LIMIT + 1}–{HARD_LINE_LIMIT} lines trigger a soft advisory only."
    ),
    "R002": "print() in src/ - use utils/logging.py",
    "R003": "swallowed error (`except: pass`) - log-and-(re)raise",
    "R004": "raise Exception(...) - use a typed error from utils/errors.py",
    "R005": "Cypher/transaction outside graph/ - move it into graph/<domain>_queries.py",
    "R006": "function/method exceeds 40 lines - extract a named helper",
    "R007": "demo_game imports npc_engine - use the HTTP client only",
}


def _print_group(title: str, signatures: set[str]) -> None:
    """Print a grouped, rule-annotated list of signatures."""
    print(title)
    for sig in sorted(signatures):
        rule, rel = sig.split("|", 1)
        print(f"  [{rule}] {rel}\n        -> {_RULE_HELP.get(rule, '')}")


def _run_check(
    current: set[str],
    baseline_path: Path,
    label: str,
    update_flag: bool,
    advisories: set[str] | None = None,
) -> int:
    """Run the ratchet check for a given set of violations against a baseline file.

    R001 uses line-count-aware comparison (_compare_r001); all other rules use
    exact-set difference. Soft advisories are printed but never affect the exit code.

    Args:
        current: Set of current violation signatures.
        baseline_path: Path to the baseline file.
        label: Human-readable label (e.g. "check-rules").
        update_flag: If True, persist current as the new baseline and exit 0.
        advisories: Optional set of R001-SOFT signatures to print as info.
    Returns:
        Exit code: 0 on pass, 1 on new violations.
    """
    if update_flag:
        _write_baseline(current, baseline_path)
        print(f"{label}: baseline updated - {len(current)} grandfathered violation(s).")
        return 0

    baseline = _load_baseline(baseline_path)

    current_r001 = {s for s in current if s.startswith("R001|")}
    current_other = current - current_r001
    baseline_r001 = {s for s in baseline if s.startswith("R001|")}
    baseline_other = baseline - baseline_r001

    new_r001, resolved_r001 = _compare_r001(current_r001, baseline_r001)
    new_other = current_other - baseline_other
    resolved_other = baseline_other - current_other

    new = new_r001 | new_other
    resolved = resolved_r001 | resolved_other

    if advisories:
        for sig in sorted(advisories):
            _, rest = sig.split("|", 1)
            print(f"  [R001-SOFT] {rest} — exceeds {SOFT_LINE_LIMIT} lines (advisory; no gate)")

    if resolved:
        print(f"{label}: {len(resolved)} baselined violation(s) resolved - run the update target to ratchet down.")
    if new:
        _print_group(f"\n{label}: FAIL - {len(new)} NEW rule violation(s):", new)
        print("\nFor R001: no waiver available — split the file. For other rules: add a DECISIONS.md entry and re-baseline.")
        return 1
    print(f"{label}: OK - no new violations ({len(baseline)} grandfathered).")
    return 0


def main() -> int:
    """Run the gate. Exit 1 on any new violation; 0 otherwise."""
    parser = argparse.ArgumentParser(description="Enforce CLAUDE.md rules with a baseline ratchet.")
    parser.add_argument("--update-baseline", action="store_true", help="Persist the current set as the baseline.")
    parser.add_argument("--evals", action="store_true", help="Check evals/ instead of src/+demo_game/.")
    parser.add_argument("--update-evals-baseline", action="store_true", help="Persist the evals/ set as its baseline.")
    args = parser.parse_args()

    if args.evals or args.update_evals_baseline:
        current, advisories = _collect_evals()
        return _run_check(current, EVALS_BASELINE_PATH, "check-evals-rules", args.update_evals_baseline, advisories)

    current, advisories = _collect()
    return _run_check(current, BASELINE_PATH, "check-rules", args.update_baseline, advisories)


if __name__ == "__main__":
    raise SystemExit(main())
