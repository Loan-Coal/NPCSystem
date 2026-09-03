"""
Module: tests.unit.scripts.test_packaging_spec
Layer: tests
Purpose: Pin the PyInstaller spec's bundled-asset list (R5.3, CR-L12-02) — every source
         path in packaging/npc_engine.spec must exist, and the spec must bundle every
         runtime asset pattern that pyproject.toml's package-data declares.
Dependencies: ast, pathlib, tomllib, pytest
Used by: make test (pytest discovery), make check via test-cov

Why this exists: `make package` has never built. The spec named REPO_ROOT/"config" and
REPO_ROOT/"game_schema.yaml", neither of which exists at the repo root — the real files
live under src/npc_engine/. A path that nothing resolves is invisible until someone runs
PyInstaller, which no gate did. Worse, the spec bundled 3 of the 11 asset patterns
pyproject.toml already declares as package data, so a build that "succeeded" would still
ship an engine with no llm_config.yaml and no type registry.

Static parse only — the spec is NOT importable (PyInstaller injects SPECPATH at build
time), so this reads it with ast and never executes it.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SPEC_PATH = _REPO_ROOT / "packaging" / "npc_engine.spec"
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"
_PACKAGE_ROOT = _REPO_ROOT / "src" / "npc_engine"
_ANALYSIS_CALL = "Analysis"
_DATAS_KEYWORD = "datas"


def _path_bindings() -> dict[str, Path]:
    """Return the spec's own module-level Path names, evaluated as PyInstaller would.

    The bindings are read from the spec source rather than assumed, because the spec
    derives them from SPECPATH — which PyInstaller sets to the directory CONTAINING
    the spec (packaging/), not the repo root. Assuming the intended value here would
    make this gate green while the build was broken.
    """
    bindings: dict[str, Path] = {"SPECPATH": _SPEC_PATH.parent}
    tree = ast.parse(_SPEC_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            bindings[target.id] = _eval_path(node.value, bindings)
    return bindings


def _eval_path(node: ast.expr, bindings: dict[str, Path]) -> Path:
    """Resolve a `REPO_ROOT / "a" / "b"` style expression to a concrete Path.

    Args:
        node: Expression node, optionally wrapped in a `str(...)` call.
        bindings: Module-level Path names the spec defines.

    Returns:
        The resolved filesystem path.

    Raises:
        AssertionError: When the expression uses a form this parser does not model.
    """
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"str", "Path"}:
        return _eval_path(node.args[0], bindings)
    if isinstance(node, ast.Name):
        assert node.id in bindings, f"spec uses unknown path name {node.id!r}"
        return bindings[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        right = node.right
        assert isinstance(right, ast.Constant) and isinstance(right.value, str), (
            "spec joins a path with a non-literal segment; this parser cannot model it"
        )
        return _eval_path(node.left, bindings) / right.value
    raise AssertionError(f"unsupported path expression: {ast.dump(node)}")


def _find_analysis_call(tree: ast.Module) -> ast.Call:
    """Return the spec's Analysis(...) call node."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == _ANALYSIS_CALL:
            return node
    raise AssertionError(f"no {_ANALYSIS_CALL}(...) call found in the spec")


def _find_datas(tree: ast.Module) -> ast.expr:
    """Return the `datas=` keyword value of the spec's Analysis(...) call."""
    for keyword in _find_analysis_call(tree).keywords:
        if keyword.arg == _DATAS_KEYWORD:
            return keyword.value
    raise AssertionError(f"no {_ANALYSIS_CALL}(..., {_DATAS_KEYWORD}=[...]) found in the spec")


def read_spec_datas() -> list[tuple[Path, str]]:
    """Return the spec's bundled assets as (source path, bundle destination) pairs."""
    tree = ast.parse(_SPEC_PATH.read_text(encoding="utf-8"))
    datas = _find_datas(tree)
    assert isinstance(datas, (ast.List, ast.Tuple)), "datas= must be a list literal"
    pairs: list[tuple[Path, str]] = []
    bindings = _path_bindings()
    for element in datas.elts:
        assert isinstance(element, ast.Tuple) and len(element.elts) == 2, (
            "each datas entry must be a (source, destination) 2-tuple"
        )
        source, destination = element.elts
        assert isinstance(destination, ast.Constant) and isinstance(destination.value, str)
        pairs.append((_eval_path(source, bindings), destination.value))
    return pairs


def read_spec_entry_script() -> Path:
    """Return the script path passed as Analysis()'s first positional argument."""
    tree = ast.parse(_SPEC_PATH.read_text(encoding="utf-8"))
    call = _find_analysis_call(tree)
    scripts = call.args[0]
    assert isinstance(scripts, (ast.List, ast.Tuple)) and scripts.elts, (
        "Analysis()'s first argument must be a non-empty list of entry scripts"
    )
    return _eval_path(scripts.elts[0], _path_bindings())


def read_package_data_patterns() -> list[str]:
    """Return pyproject's package-data glob patterns for the npc_engine package."""
    config = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["npc_engine"]
    return [str(pattern) for pattern in patterns]


def _is_bundled(asset: Path, sources: list[Path]) -> bool:
    """Return True when asset is the source itself or sits under a bundled directory."""
    return any(asset == source or source in asset.parents for source in sources)


def test_every_bundled_path_exists() -> None:
    missing = [source for source, _ in read_spec_datas() if not source.exists()]
    assert not missing, (
        "packaging/npc_engine.spec bundles paths that do not exist:\n"
        + "\n".join(f"  {path.relative_to(_REPO_ROOT).as_posix()}" for path in missing)
    )


def test_spec_bundles_every_package_data_pattern() -> None:
    sources = [source for source, _ in read_spec_datas()]
    uncovered: dict[str, list[str]] = {}
    for pattern in read_package_data_patterns():
        matches = [path for path in _PACKAGE_ROOT.glob(pattern) if path.is_file()]
        missed = [path for path in matches if not _is_bundled(path, sources)]
        if missed:
            uncovered[pattern] = [path.relative_to(_PACKAGE_ROOT).as_posix() for path in missed]
    assert not uncovered, (
        "pyproject declares runtime assets the PyInstaller spec does not bundle:\n"
        + "\n".join(f"  {pattern}: {len(files)} file(s), e.g. {files[0]}" for pattern, files in uncovered.items())
    )


def test_entry_script_exists() -> None:
    script = read_spec_entry_script()
    assert script.exists(), (
        "packaging/npc_engine.spec's Analysis() entry script does not resolve: "
        f"{script} — SPECPATH is the spec's own directory, not the repo root."
    )


def test_datas_parser_rejects_an_unmodelled_path_expression() -> None:
    node = ast.parse("some_call()", mode="eval").body
    with pytest.raises(AssertionError, match="unsupported path expression"):
        _eval_path(node, _path_bindings())
