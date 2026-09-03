"""
Module: tests.unit.scripts.test_migration_contract
Layer: tests
Purpose: The RED anchor for R5.4 (CR-L04-01/05/06). Every migration in
         scripts/migrations/ must declare an id, what it migrates, how reversible it
         is, and expose a down path.
Dependencies: ast, pathlib, pytest
Used by: make test (pytest discovery), make check via test-cov-evals

Measured before this landed: 0 of 6 migrations declared MIGRATES (so the existing
check_migrations.py gate's own contract was satisfied by nothing and carried entirely by
node_type_snapshot.json), 0 of 6 had any down/rollback path, and nothing anywhere
recorded that a migration had run — so re-running one silently re-applied it.

Static AST parse, no import: these modules connect to Neo4j at module scope in two
cases, and a unit test does no I/O. scripts/ has no __init__.py by design — six existing
test files rely on the top-level-import idiom — so the files are read, not imported.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS_DIR = _REPO_ROOT / "scripts" / "migrations"
_REVERSIBILITY = {"full", "partial", "none"}


def migration_paths() -> list[Path]:
    """Return every real migration module, excluding shared _-prefixed helpers."""
    return sorted(p for p in _MIGRATIONS_DIR.glob("*.py") if not p.name.startswith("_"))


def _module_constants(tree: ast.Module) -> dict[str, object]:
    """Return module-level literal assignments, keyed by name."""
    constants: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return constants


def _function_names(tree: ast.Module) -> set[str]:
    """Return the names of every module-level function, sync or async."""
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _parse(path: Path) -> tuple[dict[str, object], set[str]]:
    """Return (module constants, module-level function names) for one migration."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return _module_constants(tree), _function_names(tree)


def test_migrations_directory_is_not_empty() -> None:
    assert migration_paths(), "no migrations found; the glob or the directory moved"


@pytest.mark.parametrize("path", migration_paths(), ids=lambda p: p.stem)
def test_migration_declares_its_identity(path: Path) -> None:
    constants, _ = _parse(path)
    assert constants.get("MIGRATION_ID") == path.stem, (
        f"{path.name} must declare MIGRATION_ID = {path.stem!r} so the applied-state "
        "ledger has a stable key"
    )


@pytest.mark.parametrize("path", migration_paths(), ids=lambda p: p.stem)
def test_migration_declares_what_it_migrates(path: Path) -> None:
    constants, _ = _parse(path)
    assert "MIGRATES" in constants, (
        f"{path.name} must declare MIGRATES = [(node_type, field), ...] — the contract "
        "scripts/check_migrations.py reads. An empty list is a valid answer for a "
        "migration that backfills no required field."
    )
    declared = constants["MIGRATES"]
    assert isinstance(declared, list), f"{path.name}: MIGRATES must be a list"
    for pair in declared:
        assert isinstance(pair, tuple) and len(pair) == 2, f"{path.name}: {pair!r} is not a 2-tuple"
        assert all(isinstance(item, str) for item in pair), f"{path.name}: {pair!r} must be strings"


@pytest.mark.parametrize("path", migration_paths(), ids=lambda p: p.stem)
def test_migration_has_a_down_path(path: Path) -> None:
    constants, functions = _parse(path)
    reversible = constants.get("REVERSIBLE")
    assert reversible in _REVERSIBILITY, (
        f"{path.name} must declare REVERSIBLE as one of {sorted(_REVERSIBILITY)}; got {reversible!r}"
    )
    assert "down" in functions, (
        f"{path.name} must define down(). A migration that cannot be undone declares "
        'REVERSIBLE = "none" and raises from down() — that is louder than no function.'
    )
    if reversible != "full":
        reason = constants.get("IRREVERSIBLE_REASON")
        assert isinstance(reason, str) and reason.strip(), (
            f'{path.name} declares REVERSIBLE = "{reversible}" and must give a non-empty '
            "IRREVERSIBLE_REASON saying exactly what down() cannot restore"
        )
