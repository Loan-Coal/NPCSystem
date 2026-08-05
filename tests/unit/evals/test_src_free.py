"""
Module: test_src_free
Layer: test (unit)
Purpose: Mechanically enforce the EVAL-P0.2 src-free constraint — every evals/ module
         except engine_adapter.py must not contain any Python import from npc_engine.
Dependencies: ast, pathlib
Used by: pytest (make test / make check)

Why this exists: retrieval_runner.py carried five lazy npc_engine imports inline for months.
Nothing in the gate caught them because rules / lint scope only cover src/. A rule no test
enforces silently decays; this scans the AST so the constraint fails loudly when violated.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EVALS_DIR = _REPO_ROOT / "evals"
_PERMITTED_FILE = "engine_adapter.py"


def find_npc_engine_imports(source: str, filename: str) -> list[str]:
    """Return human-readable descriptions of every npc_engine import in one module.

    Walks the full AST (including function-local lazy imports) and reports any
    ``import npc_engine.*`` or ``from npc_engine.*`` statement found.

    Args:
        source: Python source text.
        filename: Basename used in violation messages.

    Returns:
        A list of violation strings; empty means the module is compliant.
    """
    tree = ast.parse(source, filename=filename)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "npc_engine" or alias.name.startswith("npc_engine."):
                    violations.append(
                        f"{filename}:{node.lineno} imports npc_engine directly ({alias.name})"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "npc_engine" or module.startswith("npc_engine."):
                violations.append(
                    f"{filename}:{node.lineno} imports from {module}"
                )
    return violations


# ── detector self-tests ────────────────────────────────────────────────────────

_BAD_TOPLEVEL = "from npc_engine.config import get_settings\n"

_BAD_LAZY = """
async def _main():
    from npc_engine.graph.infra.db import GraphDB
    return GraphDB()
"""

_GOOD_ADAPTER = """
from npc_engine.config import get_settings

async def build_retrieval_stack():
    return get_settings()
"""

_GOOD_CLEAN = """
from evals.engine_adapter import build_retrieval_stack
import asyncio
"""


def test_detector_flags_toplevel_import() -> None:
    found = find_npc_engine_imports(_BAD_TOPLEVEL, "fake.py")
    assert len(found) == 1 and "npc_engine" in found[0]


def test_detector_flags_lazy_import_inside_function() -> None:
    found = find_npc_engine_imports(_BAD_LAZY, "fake.py")
    assert len(found) == 1 and "npc_engine" in found[0]


def test_detector_returns_empty_for_clean_module() -> None:
    assert find_npc_engine_imports(_GOOD_CLEAN, "fake.py") == []


def test_detector_would_find_engine_adapter_imports() -> None:
    """engine_adapter.py itself will contain npc_engine imports — detector sees them."""
    found = find_npc_engine_imports(_GOOD_ADAPTER, "engine_adapter.py")
    assert len(found) == 1


# ── guard: glob must not be empty ──────────────────────────────────────────────


def _evals_py_files() -> list[Path]:
    """All .py files in the top-level evals/ directory."""
    return sorted(_EVALS_DIR.glob("*.py"))


def test_scan_covers_known_modules() -> None:
    """Guard the guard: if the glob returns nothing, all tests pass vacuously."""
    names = {p.name for p in _evals_py_files()}
    for expected in ("retrieval_runner.py", "runner.py", "matchers.py"):
        assert expected in names, f"{expected} not found in evals/ — glob is wrong"


# ── the real scan ──────────────────────────────────────────────────────────────


def test_only_engine_adapter_imports_npc_engine() -> None:
    """Every evals/*.py except engine_adapter.py must be src-free (no npc_engine imports)."""
    violations: list[str] = []
    for path in _evals_py_files():
        if path.name == _PERMITTED_FILE:
            continue
        source = path.read_text(encoding="utf-8")
        violations.extend(find_npc_engine_imports(source, path.name))
    assert not violations, (
        "src-free constraint violated — only engine_adapter.py may import from npc_engine:\n"
        + "\n".join(violations)
    )
