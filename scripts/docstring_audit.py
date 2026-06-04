"""
Module: docstring_audit
Layer: config
Purpose: CI gate — scan all src/npc_engine/**/*.py and report files missing
         mandatory docstring fields (Layer:, Purpose:, and for __init__.py Public surface:).
Dependencies: pathlib, ast, json, sys
Used by: make check-docstrings, CI pipeline
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def _extract_module_docstring(source: str) -> str | None:
    """Return the module-level docstring text, or None if absent."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if tree.body and isinstance(tree.body[0], ast.Expr):
        node = tree.body[0].value
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
    return None


def _check_file(path: Path) -> list[str]:
    """Return list of missing field names for the given file."""
    source = path.read_text(encoding="utf-8")
    docstring = _extract_module_docstring(source)
    if docstring is None:
        required = ["Layer:", "Purpose:"]
        if path.name == "__init__.py":
            required.append("Public surface:")
        return required

    missing: list[str] = []
    for field in ["Layer:", "Purpose:"]:
        if field not in docstring:
            missing.append(field)
    if path.name == "__init__.py" and "Public surface:" not in docstring:
        missing.append("Public surface:")
    return missing


def audit(src_root: Path) -> list[dict]:
    """Scan src_root recursively and return findings for files with missing fields."""
    findings: list[dict] = []
    for path in sorted(src_root.rglob("*.py")):
        missing = _check_file(path)
        if missing:
            findings.append({"file": str(path.relative_to(src_root.parent)), "missing_fields": missing})
    return findings


def main() -> int:
    """Run audit; print JSON findings; exit 1 if any file has missing fields."""
    repo_root = Path(__file__).parent.parent
    src_root = repo_root / "src" / "npc_engine"
    findings = audit(src_root)
    print(json.dumps(findings, indent=2))
    if findings:
        print(f"\n{len(findings)} file(s) missing mandatory docstring fields.", file=sys.stderr)
        return 1
    print("All docstrings OK.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
