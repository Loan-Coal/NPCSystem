#!/usr/bin/env python
"""
Module: check_dead_surface
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Gate dead surface — reports Settings fields with no live reader outside
         config.py, prompt YAMLs no code loads, engine contracts with no matching
         engine directory, and graph modules with no importer outside graph/.
         Rule 3. Findings: L10 dead-surface sweep, L12-15, ISSUE-332.
Dependencies: stdlib only (argparse, ast, pathlib, re, sys, textwrap).
Used by: `make check-dead-surface`, scripts/loop_gates.py.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import textwrap
from pathlib import Path
from typing import NamedTuple, Sequence

_SRC_REL = Path("src/npc_engine")
_CONFIG_REL = _SRC_REL / "config.py"

# YAML directories to scan for dead prompts
_PROMPT_ROOTS: tuple[Path, ...] = (
    _SRC_REL / "prompts",
    Path("prompts") / "eval",
)

_CONTRACTS_REL = _SRC_REL / "engines" / "contracts"
_GRAPH_REL = _SRC_REL / "graph"

# Prefixes of Python files that are part of the config definition layer.
# The Settings class is defined here, and these files are excluded from the
# "reader" search to avoid flagging the definition as its own reader.
_CONFIG_LAYER_SUFFIXES: tuple[str, ...] = (
    "config.py",
    "config_validators.py",
    "config_logging_validators.py",
    "config_prompt_window.py",
)


class DeadSurfaceItem(NamedTuple):
    """One dead-surface finding."""

    kind: str    # "settings_field" | "prompt_yaml" | "contract" | "graph_module"
    path: str    # field name, file path, or module path
    detail: str  # human-readable explanation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _word_re(name: str) -> re.Pattern[str]:
    """Compile a word-boundary pattern for name."""
    return re.compile(r"\b" + re.escape(name) + r"\b")


def _collect_py_files(root: Path) -> list[Path]:
    """Return .py files under root/src/npc_engine (production source only)."""
    src = root / _SRC_REL
    if not src.exists():
        return []
    return list(src.rglob("*.py"))


def _collect_all_py_files(root: Path) -> list[Path]:
    """Return all .py files in the repo (src, tests, evals, e2e, scripts, demo_game)."""
    result: list[Path] = []
    for subdir in ("src", "tests", "evals", "e2e", "scripts", "demo_game"):
        d = root / subdir
        if d.exists():
            result.extend(p for p in d.rglob("*.py") if "__pycache__" not in str(p))
    return result


# ---------------------------------------------------------------------------
# Settings fields
# ---------------------------------------------------------------------------


def _collect_settings_fields(root: Path) -> frozenset[str]:
    """Parse the Settings class in config.py and return all annotated field names."""
    config_py = root / _CONFIG_REL
    if not config_py.exists():
        return frozenset()
    text = config_py.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return frozenset()
    fields: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    fields.append(item.target.id)
    return frozenset(fields)


def _check_dead_settings(root: Path, py_files: Sequence[Path]) -> list[DeadSurfaceItem]:
    """Return Settings fields with no reference outside the config layer."""
    fields = _collect_settings_fields(root)
    if not fields:
        return []

    # Files to exclude: config layer definitions only
    config_layer: set[str] = set()
    for py in py_files:
        if any(py.name == s for s in _CONFIG_LAYER_SUFFIXES):
            config_layer.add(str(py))

    reader_files = [p for p in py_files if str(p) not in config_layer]

    dead: list[DeadSurfaceItem] = []
    for field in sorted(fields):
        pattern = _word_re(field)
        found = any(pattern.search(p.read_text(encoding="utf-8", errors="ignore")) for p in reader_files)
        if not found:
            dead.append(DeadSurfaceItem(
                kind="settings_field",
                path=field,
                detail=f"Settings.{field} has no reader outside the config layer",
            ))
    return dead


# ---------------------------------------------------------------------------
# Prompt YAMLs — with glob-loaded directory detection
# ---------------------------------------------------------------------------


def _scan_glob_param_functions(py_file: Path) -> list[tuple[str, str]]:
    """Return (func_name, param_name) for functions that call param.glob('*.yaml')."""
    text = py_file.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    results: list[tuple[str, str]] = []
    for fn_node in ast.walk(tree):
        if not isinstance(fn_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params: set[str] = {a.arg for a in fn_node.args.args}
        for child in ast.walk(fn_node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "glob"
                and child.args
                and isinstance(child.args[0], ast.Constant)
                and child.args[0].value in ("*.yaml", "*.yml")
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id in params
            ):
                results.append((fn_node.name, child.func.value.id))
    return results


def _extract_last_path_component(node: ast.expr) -> str | None:
    """Extract the last string component from a path expression `a / 'b'` or `'b'`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        rhs = node.right
        if isinstance(rhs, ast.Constant) and isinstance(rhs.value, str):
            return rhs.value
    return None


def _scan_glob_call_dirs(py_file: Path, func_names: frozenset[str]) -> list[str]:
    """Return the last path component of arguments passed to glob-loading functions."""
    text = py_file.read_text(encoding="utf-8", errors="ignore")
    # Quick pre-filter: skip if none of the function names appear in the file
    if not any(fn in text for fn in func_names):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    # Build a variable → last-path-component map for simple assignments in any scope
    assignments: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    comp = _extract_last_path_component(node.value)
                    if comp is not None:
                        assignments[target.id] = comp

    result: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fn_name: str | None = None
        if isinstance(fn, ast.Name):
            fn_name = fn.id
        elif isinstance(fn, ast.Attribute):
            fn_name = fn.attr
        if fn_name not in func_names or not node.args:
            continue
        arg = node.args[0]
        comp = _extract_last_path_component(arg)
        if comp is None and isinstance(arg, ast.Name):
            comp = assignments.get(arg.id)
        if comp:
            result.append(comp)
    return result


def _find_glob_loaded_dirs(py_files: Sequence[Path], yaml_dirs: Sequence[Path]) -> frozenset[Path]:
    """Return YAML directories that are entirely loaded via glob('*.yaml')."""
    # Phase 1: collect names of functions that glob *.yaml from a parameter
    glob_fn_names: set[str] = set()
    for py_file in py_files:
        for fn_name, _ in _scan_glob_param_functions(py_file):
            glob_fn_names.add(fn_name)
    if not glob_fn_names:
        return frozenset()

    func_set = frozenset(glob_fn_names)

    # Phase 2: find callers and extract the directory name they pass
    glob_dir_names: set[str] = set()
    for py_file in py_files:
        for dir_name in _scan_glob_call_dirs(py_file, func_set):
            glob_dir_names.add(dir_name)

    # Phase 3: match against actual YAML directories by name
    result: set[Path] = set()
    for yaml_dir in yaml_dirs:
        if yaml_dir.name in glob_dir_names:
            result.add(yaml_dir)
    return frozenset(result)


_GATE_TEST_RE = re.compile(r"test_check_dead_surface\.py$")


def _collect_prompt_yaml_files(root: Path) -> list[Path]:
    """Return all YAML files found under the configured prompt roots."""
    result: list[Path] = []
    for prompt_root_rel in _PROMPT_ROOTS:
        prompt_root = root / prompt_root_rel
        if prompt_root.exists():
            result.extend(prompt_root.rglob("*.yaml"))
    return result


def _prompt_reader_files(py_files: Sequence[Path]) -> list[Path]:
    """Return py_files excluding the gate's own test — it mentions YAML stems to test detection."""
    return [p for p in py_files if not _GATE_TEST_RE.search(str(p))]


def _check_dead_prompts(root: Path, py_files: Sequence[Path]) -> list[DeadSurfaceItem]:
    """Return prompt YAMLs not loaded by any Python source."""
    yaml_files = _collect_prompt_yaml_files(root)
    if not yaml_files:
        return []

    yaml_dirs = list({yf.parent for yf in yaml_files})
    glob_loaded = _find_glob_loaded_dirs(list(py_files), yaml_dirs)
    search_files = _prompt_reader_files(py_files)

    dead: list[DeadSurfaceItem] = []
    for yaml_path in sorted(yaml_files):
        if yaml_path.parent in glob_loaded:
            continue
        stem = yaml_path.stem
        pattern = _word_re(stem)
        found = any(pattern.search(p.read_text(encoding="utf-8", errors="ignore")) for p in search_files)
        if not found:
            rel = yaml_path.relative_to(root)
            dead.append(DeadSurfaceItem(
                kind="prompt_yaml",
                path=str(rel),
                detail=f"No Python file references '{stem}'; not in a glob-loaded directory",
            ))
    return dead


# ---------------------------------------------------------------------------
# Engine contracts
# ---------------------------------------------------------------------------


def _load_yaml_name(yaml_path: Path) -> str | None:
    """Extract the `name:` field from a YAML file without importing PyYAML."""
    for line in yaml_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped[len("name:"):].strip().strip('"').strip("'")
    return None


def _check_dead_contracts(root: Path) -> list[DeadSurfaceItem]:
    """Return engine contracts whose name does not match any engine directory."""
    contracts_dir = root / _CONTRACTS_REL
    if not contracts_dir.exists():
        return []
    engines_dir = root / _SRC_REL / "engines"
    engine_dirs: frozenset[str] = frozenset(
        d.name for d in engines_dir.iterdir() if d.is_dir()
    ) if engines_dir.exists() else frozenset()

    dead: list[DeadSurfaceItem] = []
    for yaml_path in sorted(contracts_dir.glob("*.yaml")):
        name = _load_yaml_name(yaml_path)
        if name is None:
            continue
        # Match: exact name, or name with _engine stripped → dir name
        candidates = {name, name.removesuffix("_engine")}
        if not candidates & engine_dirs:
            dead.append(DeadSurfaceItem(
                kind="contract",
                path=yaml_path.name,
                detail=f"Contract '{name}' has no matching directory under engines/",
            ))
    return dead


# ---------------------------------------------------------------------------
# Graph modules
# ---------------------------------------------------------------------------


def _module_path_from_file(py_file: Path, src_root: Path) -> str:
    """Convert a .py file path to a dotted module path relative to src_root's parent."""
    rel = py_file.relative_to(src_root.parent)
    return str(rel).replace("\\", "/").removesuffix(".py").replace("/", ".")


def _build_graph_stem_map(graph_dir: Path) -> dict[str, Path]:
    """Return {stem: path} for all non-init Python modules under graph_dir."""
    return {
        py.stem: py
        for py in graph_dir.rglob("*.py")
        if py.name != "__init__.py"
    }


def _compute_alive_graph_modules(
    stem_to_file: dict[str, Path],
    py_files: Sequence[Path],
    graph_dir_str: str,
) -> set[Path]:
    """Return graph modules reachable via BFS from any external importer."""
    external = [p for p in py_files if graph_dir_str not in str(p).replace("\\", "/")]
    alive: set[Path] = set()
    for ext in external:
        text = ext.read_text(encoding="utf-8", errors="ignore")
        for stem, path in stem_to_file.items():
            if stem in text:
                alive.add(path)
    frontier = list(alive)
    while frontier:
        mod = frontier.pop()
        text = mod.read_text(encoding="utf-8", errors="ignore")
        for stem, path in stem_to_file.items():
            if path not in alive and stem in text:
                alive.add(path)
                frontier.append(path)
    return alive


def _check_dead_graph_modules(root: Path, py_files: Sequence[Path]) -> list[DeadSurfaceItem]:
    """Return graph modules unreachable from any importer outside graph/.

    Uses transitive BFS reachability — a module is dead if no chain of imports
    from outside graph/ reaches it (T1.2 precursor, T10.2a gate).
    """
    graph_dir = root / _GRAPH_REL
    if not graph_dir.exists():
        return []

    src_root = root / _SRC_REL
    graph_dir_str = str(graph_dir).replace("\\", "/")
    stem_to_file = _build_graph_stem_map(graph_dir)
    alive = _compute_alive_graph_modules(stem_to_file, py_files, graph_dir_str)

    dead: list[DeadSurfaceItem] = []
    for py in sorted(graph_dir.rglob("*.py")):
        if py.name == "__init__.py" or py in alive:
            continue
        mod_path = _module_path_from_file(py, src_root)
        search_key = mod_path[len("npc_engine."):]
        rel = py.relative_to(root)
        dead.append(DeadSurfaceItem(
            kind="graph_module",
            path=str(rel).replace("\\", "/"),
            detail=f"Module '{search_key}' is unreachable from outside graph/",
        ))
    return dead


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def check_dead_surface(root: Path) -> list[DeadSurfaceItem]:
    """Run all dead-surface checks and return the combined findings.

    Args:
        root: Repo root directory.

    Returns:
        List of DeadSurfaceItem findings, sorted by kind then path.
    """
    src_py_files = _collect_py_files(root)         # src/npc_engine/ only
    all_py_files = _collect_all_py_files(root)     # entire repo
    findings: list[DeadSurfaceItem] = []
    findings.extend(_check_dead_settings(root, src_py_files))
    # Prompts may be loaded from evals/, e2e/, scripts/, or demo_game/ too
    findings.extend(_check_dead_prompts(root, all_py_files))
    findings.extend(_check_dead_contracts(root))
    # Graph modules: include tests in reachability — a module with test coverage is alive
    findings.extend(_check_dead_graph_modules(root, all_py_files))
    return sorted(findings, key=lambda x: (x.kind, x.path))


def main() -> int:
    """CLI entry point: print all dead-surface findings and exit 1 if any.

    Returns:
        0 if no findings, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Gate dead surface — Settings fields, prompt YAMLs, contracts, graph modules."
    )
    parser.add_argument("--root", type=Path, default=None, help="Repo root (default: auto-detect)")
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parents[1]
    findings = check_dead_surface(root)

    if not findings:
        print("check-dead-surface: OK — no dead surface found")
        return 0

    # Group by kind for readable output
    by_kind: dict[str, list[DeadSurfaceItem]] = {}
    for item in findings:
        by_kind.setdefault(item.kind, []).append(item)

    labels = {
        "settings_field": "Dead Settings fields",
        "prompt_yaml": "Dead prompt YAMLs",
        "contract": "Orphaned engine contracts",
        "graph_module": "Dead graph modules",
    }
    for kind, items in sorted(by_kind.items()):
        print(f"\n{labels.get(kind, kind)} ({len(items)}):")
        for item in items:
            print(f"  {item.path}")
            print(textwrap.indent(item.detail, "      "))

    total = len(findings)
    print(f"\ncheck-dead-surface: FAIL — {total} finding(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
