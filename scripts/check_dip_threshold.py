#!/usr/bin/env python
"""
Module: check_dip_threshold
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: Gate the DIP abstraction threshold — every public Protocol class in
         `src/npc_engine/engines/ports/` must have 2+ structural implementors
         OR 3+ callers (files that use it as a parameter type annotation).
         Protocols below threshold must appear in scripts/dip_waivers.txt with a
         DEC-NNN decision reference; the waiver file itself is frozen so the gate
         cannot be gamed by appending a line (see loop_gates.py). An empty waiver
         file is the target state. Rule 4, DEC-275.
Dependencies: stdlib only (argparse, ast, pathlib, re, sys).
Used by: `make check-dip-threshold`, scripts/loop_gates.py.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

_PORTS_REL = Path("src/npc_engine/engines/ports")
_SRC_REL = Path("src/npc_engine")
_WAIVERS_REL = Path("scripts/dip_waivers.txt")

_MIN_IMPLEMENTORS = 2
_MIN_CALLERS = 3

_DEC_PATTERN = re.compile(r"\bDEC-\d+\b")

# Wiring files: DI composition roots that inject concrete implementations into
# protocol-typed parameters. They are not "consumers" of the interface and are
# excluded from the caller count (api/dependencies_advanced/progression.py:38,54,100
# are the known prose-mention false-positives from the pre-Sprint-5 tree).
_WIRING_REL_PREFIXES: tuple[str, ...] = (
    "api/dependencies",
    "api/dependencies_advanced/",
)


# ---------------------------------------------------------------------------
# Protocol discovery
# ---------------------------------------------------------------------------


def _parse_classes(filepath: Path) -> dict[str, dict]:
    """Return {ClassName: {methods: set[str], bases: list[str]}} for filepath."""
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    result: dict[str, dict] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            bases: list[str] = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(b.attr)
            result[node.name] = {"methods": methods, "bases": bases}
    return result


def _resolve_methods(name: str, all_classes: dict[str, dict]) -> frozenset[str]:
    """Collect all method names for name, following Protocol inheritance."""
    if name not in all_classes:
        return frozenset()
    info = all_classes[name]
    methods: set[str] = set(info["methods"])
    for base in info["bases"]:
        methods |= _resolve_methods(base, all_classes)
    return frozenset(methods)


def _is_protocol_class(name: str, all_classes: dict[str, dict]) -> bool:
    """Return True if name is a Protocol subclass (direct or indirect)."""
    if name not in all_classes:
        return False
    for base in all_classes[name]["bases"]:
        if base == "Protocol" or _is_protocol_class(base, all_classes):
            return True
    return False


def get_protocols(ports_dir: Path) -> dict[str, frozenset[str]]:
    """Return {ProtocolName: frozenset_of_all_method_names} for public protocols.

    Scans every .py file in ports_dir (excluding __init__.py) and collects public
    Protocol classes (not starting with '_').
    """
    protocols: dict[str, frozenset[str]] = {}
    for py_file in sorted(ports_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        all_classes = _parse_classes(py_file)
        for name, info in all_classes.items():
            if name.startswith("_"):
                continue
            if _is_protocol_class(name, all_classes):
                protocols[name] = _resolve_methods(name, all_classes)
    return protocols


# ---------------------------------------------------------------------------
# Implementor counting
# ---------------------------------------------------------------------------


def _has_all_methods(class_info: dict, required: frozenset[str]) -> bool:
    """Return True if the class directly declares all required method names."""
    if not required:
        return False
    return required.issubset(class_info["methods"])


def find_implementors(
    protocol_name: str,
    methods: frozenset[str],
    src_root: Path,
    ports_dir: Path,
) -> list[str]:
    """Return paths of files containing concrete classes that structurally satisfy
    the protocol by defining all its method names.

    Concrete class = any class not having Protocol in its MRO. Protocol files
    themselves are excluded. Returns file paths relative to src_root.
    """
    implementors: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        try:
            py_file.relative_to(ports_dir)
            continue  # skip port files
        except ValueError:
            pass
        all_classes = _parse_classes(py_file)
        for cls_name, info in all_classes.items():
            if _is_protocol_class(cls_name, all_classes):
                continue  # skip Protocol classes themselves
            if _has_all_methods(info, methods):
                rel = str(py_file.relative_to(src_root)).replace("\\", "/")
                implementors.append(rel)
                break  # one implementor per file is enough
    return implementors


# ---------------------------------------------------------------------------
# Caller counting
# ---------------------------------------------------------------------------


def _strip_strings_and_comments(source: str) -> str:
    """Remove docstrings and line comments so annotations outside prose are found."""
    source = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    source = re.sub(r"'''.*?'''", "", source, flags=re.DOTALL)
    source = re.sub(r"#.*$", "", source, flags=re.MULTILINE)
    return source


def _has_import(text: str, name: str) -> bool:
    """Return True if text contains an import of name (import stmt, not prose)."""
    return bool(re.search(r"\bimport\b[^(]*\b" + re.escape(name) + r"\b", text))


def _uses_as_annotation(stripped: str, name: str) -> bool:
    """Return True if name appears as a type annotation in stripped source."""
    pattern = re.compile(r":\s*" + re.escape(name) + r"\b")
    return bool(pattern.search(stripped))


def find_callers(
    protocol_name: str,
    src_root: Path,
    ports_dir: Path,
) -> list[str]:
    """Return paths of non-port, non-wiring files that use the Protocol as a type
    annotation AND import it explicitly.

    Excludes:
    - Files inside ports_dir (including __init__.py re-exports)
    - Wiring / DI composition files (_WIRING_REL_PREFIXES)
    - Files that only mention the name in docstrings or comments (prose exclusion)
    """
    callers: list[str] = []
    for py_file in sorted(src_root.rglob("*.py")):
        # Exclude port files
        try:
            py_file.relative_to(ports_dir)
            continue
        except ValueError:
            pass

        rel = str(py_file.relative_to(src_root)).replace("\\", "/")

        # Exclude wiring files
        if any(rel.startswith(p) for p in _WIRING_REL_PREFIXES):
            continue

        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if protocol_name not in text:
            continue
        if not _has_import(text, protocol_name):
            continue

        stripped = _strip_strings_and_comments(text)
        if _uses_as_annotation(stripped, protocol_name):
            callers.append(rel)

    return callers


# ---------------------------------------------------------------------------
# Waiver file
# ---------------------------------------------------------------------------


def load_waivers(waivers_path: Path) -> dict[str, str]:
    """Return {ProtocolName: dec_reference} from the waiver file.

    Raises ValueError for any non-comment line that lacks a DEC-NNN token.
    Missing waiver file is treated as empty (no waivers).
    """
    if not waivers_path.exists():
        return {}
    waivers: dict[str, str] = {}
    for lineno, raw in enumerate(waivers_path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _DEC_PATTERN.search(line):
            raise ValueError(
                f"{waivers_path}:{lineno}: waiver line missing DEC-NNN reference: {raw!r}"
            )
        parts = line.split(None, 1)
        waivers[parts[0]] = line
    return waivers


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def _check_protocol(
    name: str,
    methods: frozenset[str],
    src_root: Path,
    ports_dir: Path,
    waivers: dict[str, str],
) -> str | None:
    """Return a violation message for name, or None if it passes the threshold.

    Passes when: implementors >= _MIN_IMPLEMENTORS OR callers >= _MIN_CALLERS OR
    an approved DEC-NNN waiver entry exists.
    """
    n_impl = len(find_implementors(name, methods, src_root, ports_dir))
    n_call = len(find_callers(name, src_root, ports_dir))
    if n_impl >= _MIN_IMPLEMENTORS or n_call >= _MIN_CALLERS:
        return None
    if name in waivers:
        return None
    return (
        f"FAIL {name}: {n_impl} implementor(s) < {_MIN_IMPLEMENTORS} "
        f"AND {n_call} caller(s) < {_MIN_CALLERS} — "
        f"add waiver to scripts/dip_waivers.txt citing a DEC-NNN decision"
    )


def check_dip_threshold(root: Path | None = None) -> list[str]:
    """Run the DIP threshold gate against root and return all violation messages.

    A violation is a public Protocol in engines/ports/ that has fewer than
    _MIN_IMPLEMENTORS structural implementors AND fewer than _MIN_CALLERS callers,
    and is not listed in scripts/dip_waivers.txt with a DEC-NNN reference.

    Args:
        root: Repository root. Defaults to the parent of scripts/.

    Returns:
        List of violation strings (empty = green).

    Raises:
        ValueError: if the waiver file contains a line missing a DEC-NNN reference.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent
    root = Path(root)
    ports_dir = root / _PORTS_REL
    src_root = root / _SRC_REL
    waivers = load_waivers(root / _WAIVERS_REL)
    if not ports_dir.is_dir():
        return []
    protocols = get_protocols(ports_dir)
    return [
        msg
        for name, methods in sorted(protocols.items())
        if (msg := _check_protocol(name, methods, src_root, ports_dir, waivers)) is not None
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; exits 0 on green, 1 on violations.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        0 for a clean run, 1 for violations.
    """
    parser = argparse.ArgumentParser(
        description="Check DIP threshold for engines/ports/ Protocol classes."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/).",
    )
    args = parser.parse_args(argv)

    waivers = load_waivers(args.root / _WAIVERS_REL)
    waiver_count = len(waivers)

    violations = check_dip_threshold(root=args.root)
    for v in violations:
        print(v)

    if violations:
        print(f"\n{len(violations)} DIP threshold violation(s) found.")
        return 1

    status = "OK check-dip-threshold"
    if waiver_count:
        status += f" ({waiver_count} active waiver(s) — target state is zero)"
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
