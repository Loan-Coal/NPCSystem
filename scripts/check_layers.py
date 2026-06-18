#!/usr/bin/env python
"""
Module: check_layers
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Enforce the NPC Engine layer model; fail CI on any upward import.
Dependencies: stdlib only.
Used by: `make check-layers`, CI static-analysis.

Parses all src/npc_engine/**/*.py files, resolves each `from npc_engine.X` import
to its package rank, and exits 1 if the importing package's rank is lower (closer to
api) than the imported package's rank.

LAYER_RANK: higher value = higher layer (closer to api).
Upward violation = importer_rank < imported_rank.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Higher rank = higher layer (api side). graph may only import config/utils/common.
# Ranks verified against actual import edges (SEV-31): world/ and mutation/ are
# imported by graph/ so they are assigned rank 2 (graph peer), not services (4).
LAYER_RANK: dict[str, int] = {
    "api": 6,
    "auth": 6,
    "data": 6,
    "engines": 5,
    "scheduler": 5,
    "services": 4,
    "cache": 4,
    "retrieval": 3,
    "graph": 2,
    "mutation": 2,
    "world": 2,
    "config": 1,
    "common": 1,
    "type_registry": 1,
    "schema": 1,
    "utils": 1,
    "observability": 1,
    # SHIP-03 / DEC-127: first-run bootstrap utilities (VRAM detection, Ollama
    # management). Peer to config — imports only stdlib and httpx, never engines.
    "setup": 1,
}

# First-level dirs that hold no layer code (dev tooling / prompt data): exempt from
# the unranked-package guard. prompts/ is YAML only; scripts/ is dev tooling.
_EXEMPT_PACKAGES: frozenset[str] = frozenset({"scripts", "prompts"})

# Packages whose rank is unknown are skipped (not violations).
_UNKNOWN_RANK = -1


def _package_of(path: Path, src_root: Path) -> str | None:
    """Return the first-level npc_engine sub-package for *path*, or None."""
    try:
        rel = path.relative_to(src_root)
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    return parts[0]


def _rank(pkg: str | None) -> int:
    if pkg is None:
        return _UNKNOWN_RANK
    return LAYER_RANK.get(pkg, _UNKNOWN_RANK)


def find_violations_in_file(
    path: Path,
    importer_pkg: str,
) -> List[Tuple[str, int, str]]:
    """Return (file, lineno, message) tuples for each upward import in *path*.

    Args:
        path: Absolute path to a Python source file.
        importer_pkg: The first-level npc_engine sub-package of the file.
    Returns:
        List of (str(path), line_number, human_readable_message) tuples.
    """
    importer_rank = _rank(importer_pkg)
    if importer_rank == _UNKNOWN_RANK:
        return []

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, OSError):
        return []

    violations: List[Tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        module: str | None = None
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                break
        if module is None:
            continue
        if not module.startswith("npc_engine."):
            continue
        parts = module.split(".")
        if len(parts) < 2:
            continue
        imported_pkg = parts[1]
        imported_rank = _rank(imported_pkg)
        if imported_rank == _UNKNOWN_RANK:
            continue
        if importer_rank < imported_rank:
            msg = (
                f"layer violation: '{importer_pkg}' (rank {importer_rank}) "
                f"imports '{imported_pkg}' (rank {imported_rank})"
            )
            violations.append((str(path), node.lineno, msg))
    return violations


def find_violations(src_root: Path) -> List[Tuple[str, int, str]]:
    """Scan all Python files under *src_root* and return violations.

    Args:
        src_root: Path to the npc_engine package root (contains the sub-packages).
    Returns:
        Flat list of (file, lineno, message) tuples.
    """
    all_violations: List[Tuple[str, int, str]] = []
    for py_file in src_root.rglob("*.py"):
        pkg = _package_of(py_file, src_root)
        violations = find_violations_in_file(py_file, pkg or "")
        all_violations.extend(violations)
    return all_violations


def find_unranked_packages(src_root: Path) -> List[Tuple[str, int, str]]:
    """Flag first-level package dirs that hold Python but have no LAYER_RANK entry.

    An unranked code package is silently skipped by the import checker, so a new
    layer could bypass enforcement entirely (L2-09). Hidden dirs, `__pycache__`,
    exempt tooling, and top-level modules (files, not dirs) are not flagged.

    Args:
        src_root: Path to the npc_engine package root.
    Returns:
        List of (dir, 0, message) tuples for each unranked code package.
    """
    violations: List[Tuple[str, int, str]] = []
    for child in sorted(src_root.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if child.name in LAYER_RANK or child.name in _EXEMPT_PACKAGES:
            continue
        if any(child.rglob("*.py")):
            msg = (
                f"unranked package '{child.name}' contains Python but has no LAYER_RANK "
                f"entry — add it to LAYER_RANK or _EXEMPT_PACKAGES"
            )
            violations.append((str(child), 0, msg))
    return violations


def main() -> int:
    """Entry point for `make check-layers`.

    Returns:
        0 if no violations, 1 if any violations found.
    """
    src_root = REPO_ROOT / "src" / "npc_engine"
    violations = find_violations(src_root) + find_unranked_packages(src_root)
    if not violations:
        print("check-layers: OK — no layer violations found.")
        return 0
    for file_path, lineno, msg in violations:
        rel = Path(file_path).relative_to(REPO_ROOT)
        print(f"{rel}:{lineno}: {msg}")
    print(f"\ncheck-layers: FAIL — {len(violations)} violation(s) found.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
