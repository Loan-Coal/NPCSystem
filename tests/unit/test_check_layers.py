"""
Tests for scripts/check_layers.py layer enforcement.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


def _import_checker():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "check_layers",
        Path(__file__).resolve().parent.parent.parent / "scripts" / "check_layers.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_violations_for_same_layer(tmp_path):
    checker = _import_checker()
    # engine (5) importing services (4) — legal downward
    src = textwrap.dedent("""\
        from npc_engine.services.foo import Bar
    """)
    (tmp_path / "my_engine.py").write_text(src)
    violations = checker.find_violations_in_file(tmp_path / "my_engine.py", "engines")
    assert violations == []


def test_detects_upward_violation(tmp_path):
    checker = _import_checker()
    # graph (2) importing retrieval (3) — upward violation
    src = textwrap.dedent("""\
        from npc_engine.retrieval.embedding_index import EmbeddingIndex
    """)
    (tmp_path / "bad.py").write_text(src)
    violations = checker.find_violations_in_file(tmp_path / "bad.py", "graph")
    assert len(violations) == 1
    assert "retrieval" in violations[0][2]
    assert "graph" in violations[0][2]


def test_detects_engines_importing_api(tmp_path):
    checker = _import_checker()
    # engines (5) importing api (6) — upward violation
    src = textwrap.dedent("""\
        from npc_engine.api.dependencies import get_type_registry
    """)
    (tmp_path / "handler.py").write_text(src)
    violations = checker.find_violations_in_file(tmp_path / "handler.py", "engines")
    assert len(violations) == 1


def test_src_tree_clean_after_fixes():
    """After SEV-31 fixes the src tree must have zero layer violations."""
    checker = _import_checker()
    src_root = Path(__file__).resolve().parent.parent.parent / "src" / "npc_engine"
    violations = checker.find_violations(src_root)
    if violations:
        msgs = "\n".join(f"{f}:{ln}: {msg}" for f, ln, msg in violations)
        pytest.fail(f"Layer violations found:\n{msgs}")


# ── SEV-10: observability ranked + unranked-package guard ──────────────────────


def test_observability_is_ranked():
    """observability/ must be ranked so future Python there is layer-checked (L2-09)."""
    checker = _import_checker()
    assert checker.LAYER_RANK.get("observability") == 1


def test_unranked_code_package_is_flagged(tmp_path):
    """A first-level dir with .py but no LAYER_RANK entry must be reported, not skipped."""
    checker = _import_checker()
    pkg = tmp_path / "rogue"
    pkg.mkdir()
    (pkg / "mod.py").write_text("x = 1\n")
    violations = checker.find_unranked_packages(tmp_path)
    assert any("rogue" in msg for _, _, msg in violations)


def test_ranked_and_exempt_packages_not_flagged(tmp_path):
    """Ranked packages, exempt tooling (scripts), and __pycache__ are not flagged."""
    checker = _import_checker()
    for name in ("graph", "scripts", "__pycache__"):
        d = tmp_path / name
        d.mkdir()
        (d / "x.py").write_text("x = 1\n")
    assert checker.find_unranked_packages(tmp_path) == []


def test_real_src_tree_has_no_unranked_packages():
    """The real tree must be fully ranked/exempt (scripts exempt, prompts has no .py)."""
    checker = _import_checker()
    src_root = Path(__file__).resolve().parent.parent.parent / "src" / "npc_engine"
    assert checker.find_unranked_packages(src_root) == []
