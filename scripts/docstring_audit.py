"""
Module: docstring_audit
Layer: config
Purpose: CI gate — scan src/npc_engine/**/*.py and evals/**/*.py for files missing
         mandatory docstring fields and for invalid or directory-mismatched Layer: values.
Dependencies: pathlib, ast, json, sys
Used by: make check-docstrings, CI pipeline
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

# Primary layer names from the CLAUDE.md rank model.
# Each declared layer is the canonical name for one rank group.
# Peer directories (auth, data, scheduler, cache, mutation, world, common,
# type_registry, schema, utils) use the primary name of their rank group.
DECLARED_LAYERS: frozenset[str] = frozenset({
    "api",        # rank 6: api/, auth/, data/
    "engines",    # rank 5: engines/, scheduler/
    "services",   # rank 4: services/, cache/
    "retrieval",  # rank 3: retrieval/
    "graph",      # rank 2: graph/, mutation/, world/
    "config",     # rank 1: config/, common/, type_registry/, schema/, utils/
    "evals",      # eval harness: evals/
})

# Maps top-level directory name → expected Layer: value for files inside it.
# Directories absent from this map (e.g. scripts/) have no directory constraint;
# they only require the layer value to be a declared name.
DIR_TO_EXPECTED_LAYER: dict[str, str] = {
    "api": "api", "auth": "api", "data": "api",
    "engines": "engines", "scheduler": "engines",
    "services": "services", "cache": "services",
    "retrieval": "retrieval",
    "graph": "graph", "mutation": "graph", "world": "graph",
    "config": "config", "common": "config",
    "type_registry": "config", "schema": "config", "utils": "config",
}

PLACEHOLDER_PURPOSE_TEXT = "(auto-detected — review)"


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


def _extract_layer(docstring: str) -> str | None:
    """Return the first-token layer value from a docstring, or None if absent."""
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped.startswith("Layer:"):
            value = stripped[6:].strip()
            return value.split()[0] if value else None
    return None


def _expected_layer_for(path: Path, src_root: Path) -> str | None:
    """Return the expected Layer: value for a file given its root, or None if unconstrained.

    None means only the declared-layer check applies (no directory constraint).
    """
    rel = path.relative_to(src_root)
    parts = rel.parts
    if len(parts) <= 1:
        return None  # root-level file: no directory constraint
    top_dir = parts[0]
    return DIR_TO_EXPECTED_LAYER.get(top_dir)  # None when directory is not mapped


def _check_file(path: Path, src_root: Path | None = None) -> list[str]:
    """Return list of missing or invalid field descriptions for the given file."""
    source = path.read_text(encoding="utf-8")
    docstring = _extract_module_docstring(source)
    if docstring is None:
        required = ["Layer:", "Purpose:"]
        if path.name == "__init__.py":
            required.append("Public surface:")
        return required

    missing: list[str] = []
    if "Purpose:" not in docstring:
        missing.append("Purpose:")
    if path.name == "__init__.py" and "Public surface:" not in docstring:
        missing.append("Public surface:")
    if PLACEHOLDER_PURPOSE_TEXT in docstring:
        missing.append("Purpose: placeholder")

    layer = _extract_layer(docstring)
    if layer is None:
        missing.append("Layer:")
    elif layer not in DECLARED_LAYERS:
        missing.append(f"Layer: invalid value {layer!r}")
    elif src_root is not None:
        expected = _expected_layer_for(path, src_root)
        if expected is not None and layer != expected:
            missing.append(f"Layer: expected {expected!r}, got {layer!r}")

    return missing


def audit(src_root: Path) -> list[dict]:
    """Scan src_root recursively and return findings for files with missing or invalid fields."""
    findings: list[dict] = []
    for path in sorted(src_root.rglob("*.py")):
        missing = _check_file(path, src_root=src_root)
        if missing:
            findings.append({"file": str(path.relative_to(src_root.parent)), "missing_fields": missing})
    return findings


def main() -> int:
    """Run audit; print JSON findings; exit 1 if any file has missing fields."""
    repo_root = Path(__file__).parent.parent
    src_root = repo_root / "src" / "npc_engine"
    evals_root = repo_root / "evals"

    src_findings = audit(src_root)
    evals_findings = audit(evals_root)
    findings = src_findings + evals_findings

    print(json.dumps(findings, indent=2))
    if findings:
        print(f"\n{len(findings)} file(s) missing mandatory docstring fields.", file=sys.stderr)
        return 1
    print("All docstrings OK.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
