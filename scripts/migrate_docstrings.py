"""
Module: migrate_docstrings
Layer: config
Purpose: One-shot migration script that adds missing Layer:/Purpose:/Public surface: fields
         to module docstrings across src/npc_engine/, inferred from package path.
Dependencies: pathlib, ast, re, sys
Used by: manual run (python scripts/migrate_docstrings.py)
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Layer inference: map package-path segments to canonical layer names.
_LAYER_MAP: list[tuple[str, str]] = [
    ("api", "api"),
    ("auth", "api"),
    ("data", "api"),
    ("engines", "engines"),
    ("scheduler", "engines"),
    ("services", "services"),
    ("mutation", "services"),
    ("cache", "services"),
    ("world", "services"),
    ("retrieval", "retrieval"),
    ("graph", "graph"),
    ("config", "config"),
    ("schema", "config"),
    ("type_registry", "config"),
    ("common", "config"),
    ("utils", "config"),
]


def _infer_layer(rel_path: Path) -> str:
    """Infer layer from relative path parts; return 'unknown' if unrecognised."""
    parts = rel_path.parts
    # parts[0] == 'npc_engine', parts[1] is the sub-package
    for segment in parts[1:]:
        for key, layer in _LAYER_MAP:
            if segment == key:
                return layer
    return "unknown"


def _extract_docstring_bounds(source: str) -> tuple[int, int] | None:
    """Return (start_char, end_char) of the module docstring incl. quotes, or None."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if not tree.body:
        return None
    first = tree.body[0]
    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)):
        return None
    if not isinstance(first.value.value, str):
        return None
    # ast gives us line/col numbers; use regex to find the literal in the source.
    # Search for the first triple-quote block at the very top (after optional whitespace).
    m = re.match(r'\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', source)
    if m:
        return m.start(1), m.end(1)
    return None


def _build_new_docstring(
    old_body: str, layer: str, is_init: bool
) -> str:
    """Return a replacement docstring body (the text inside the quotes)."""
    has_layer = "Layer:" in old_body
    has_purpose = "Purpose:" in old_body
    has_surface = "Public surface:" in old_body

    lines = old_body.rstrip().splitlines()
    # Remove trailing empty line(s) from the body we'll reconstruct.
    while lines and not lines[-1].strip():
        lines.pop()

    additions: list[str] = []
    if not has_layer:
        additions.append(f"Layer: {layer}")
    if not has_purpose:
        additions.append("Purpose: (auto-detected — review)")
    if is_init and not has_surface:
        additions.append("Public surface: (list re-exports here)")

    if not additions:
        return old_body  # nothing to do

    # Insert after the first non-empty line (the module name / title line).
    insert_after = 0
    for i, line in enumerate(lines):
        if line.strip():
            insert_after = i
            break

    new_lines = lines[: insert_after + 1] + additions + lines[insert_after + 1 :]
    return "\n".join(new_lines) + "\n"


def migrate_file(path: Path, src_root: Path) -> bool:
    """Migrate docstring in-place; return True if file was modified."""
    source = path.read_text(encoding="utf-8")
    rel = path.relative_to(src_root.parent)  # relative to src/
    layer = _infer_layer(rel)
    is_init = path.name == "__init__.py"

    bounds = _extract_docstring_bounds(source)
    if bounds is None:
        # No module docstring at all — inject a minimal one.
        name = path.stem if not is_init else path.parent.name
        if is_init:
            new_doc = (
                f'"""\nPackage: {name}\nLayer: {layer}\n'
                f"Purpose: (auto-detected — review)\n"
                f"Public surface: (list re-exports here)\n\"\"\"\n"
            )
        else:
            new_doc = (
                f'"""\nModule: {name}\nLayer: {layer}\n'
                f"Purpose: (auto-detected — review)\n"
                f"Dependencies: (auto-detected — review)\n"
                f"Used by: (auto-detected — review)\n\"\"\"\n"
            )
        source = new_doc + source
        path.write_text(source, encoding="utf-8")
        return True

    start, end = bounds
    quote_char = source[start : start + 3]
    old_body = source[start + 3 : end - 3]
    new_body = _build_new_docstring(old_body, layer, is_init)
    if new_body == old_body:
        return False

    new_source = source[:start] + quote_char + new_body + quote_char + source[end:]
    path.write_text(new_source, encoding="utf-8")
    return True


def main() -> int:
    """Migrate all flagged files; print each path modified."""
    repo_root = Path(__file__).parent.parent
    src_root = repo_root / "src" / "npc_engine"
    modified = 0
    for path in sorted(src_root.rglob("*.py")):
        if migrate_file(path, src_root):
            print(path.relative_to(repo_root))
            modified += 1
    print(f"\n{modified} file(s) updated.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
