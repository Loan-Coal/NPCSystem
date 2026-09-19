"""
Module: tests.unit.scripts.test_check_loc_ratchet
Layer: tests
Purpose: Unit tests for scripts/check_loc_ratchet.py — verifies the LOC ratchet
         gate counts non-test Python LOC across the four tracked directories,
         compares to the baseline, and fails only when the total rises.
Dependencies: pathlib, sys, pytest, check_loc_ratchet
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_loc_ratchet import (  # noqa: E402
    check_loc_ratchet,
    count_all,
    count_loc_for_dir,
    main,
    read_baseline,
    write_baseline,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(path: Path, lines: int) -> None:
    """Write a synthetic .py file with 'lines' non-blank source lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"x_{i} = {i}" for i in range(lines))
    path.write_text(content + "\n", encoding="utf-8")


def _make_baseline(path: Path, total: int) -> None:
    """Write a minimal baseline file with the given total."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"src/npc_engine: 0\nscripts: 0\nevals: 0\ndemo_game: 0\ntotal: {total}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# count_loc_for_dir
# ---------------------------------------------------------------------------


def test_count_loc_for_dir_counts_py_lines(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "util.py", 10)
    assert count_loc_for_dir(tmp_path, "scripts") == 10


def test_count_loc_for_dir_excludes_test_files(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "util.py", 10)
    _write_py(tmp_path / "scripts" / "test_util.py", 20)
    assert count_loc_for_dir(tmp_path, "scripts") == 10


def test_count_loc_for_dir_excludes_tests_subdir(tmp_path: Path) -> None:
    _write_py(tmp_path / "src" / "npc_engine" / "module.py", 15)
    _write_py(tmp_path / "src" / "npc_engine" / "tests" / "test_module.py", 30)
    assert count_loc_for_dir(tmp_path, "src/npc_engine") == 15


def test_count_loc_for_dir_missing_dir_returns_zero(tmp_path: Path) -> None:
    assert count_loc_for_dir(tmp_path, "nonexistent") == 0


def test_count_loc_for_dir_skips_pycache(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "__pycache__" / "util.cpython-311.pyc", 5)
    # .pyc files are not .py, but ensure __pycache__ exclusion works for .py too
    _write_py(tmp_path / "scripts" / "__pycache__" / "cached.py", 5)
    _write_py(tmp_path / "scripts" / "real.py", 8)
    assert count_loc_for_dir(tmp_path, "scripts") == 8


# ---------------------------------------------------------------------------
# count_all
# ---------------------------------------------------------------------------


def test_count_all_sums_all_dirs(tmp_path: Path) -> None:
    _write_py(tmp_path / "src" / "npc_engine" / "mod.py", 5)
    _write_py(tmp_path / "scripts" / "tool.py", 3)
    _write_py(tmp_path / "evals" / "eval.py", 7)
    _write_py(tmp_path / "demo_game" / "demo.py", 4)
    counts = count_all(tmp_path)
    assert counts["src/npc_engine"] == 5
    assert counts["scripts"] == 3
    assert counts["evals"] == 7
    assert counts["demo_game"] == 4
    assert counts["total"] == 19


def test_count_all_total_is_sum_of_dirs(tmp_path: Path) -> None:
    counts = count_all(tmp_path)
    assert counts["total"] == sum(
        counts[d] for d in ("src/npc_engine", "scripts", "evals", "demo_game")
    )


# ---------------------------------------------------------------------------
# read_baseline / write_baseline
# ---------------------------------------------------------------------------


def test_read_baseline_parses_entries(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "# comment\nsrc/npc_engine: 100\nscripts: 50\nevals: 20\ndemo_game: 30\ntotal: 200\n",
        encoding="utf-8",
    )
    data = read_baseline(baseline)
    assert data["src/npc_engine"] == 100
    assert data["total"] == 200


def test_read_baseline_ignores_comments(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("# not a value\ntotal: 42\n", encoding="utf-8")
    assert read_baseline(baseline)["total"] == 42


def test_read_baseline_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_baseline(tmp_path / "missing.txt") == {}


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    counts = {"src/npc_engine": 100, "scripts": 50, "evals": 20, "demo_game": 30, "total": 200}
    write_baseline(baseline, counts)
    data = read_baseline(baseline)
    assert data["total"] == 200
    assert data["src/npc_engine"] == 100


# ---------------------------------------------------------------------------
# check_loc_ratchet — unit cases on synthetic trees
# ---------------------------------------------------------------------------


def test_green_when_total_at_baseline(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "tool.py", 10)
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    _make_baseline(baseline, total=10)
    failures = check_loc_ratchet(root=tmp_path, baseline_path=baseline)
    assert failures == []


def test_green_when_total_below_baseline(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "tool.py", 5)
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    _make_baseline(baseline, total=10)
    failures = check_loc_ratchet(root=tmp_path, baseline_path=baseline)
    assert failures == []


def test_red_when_total_exceeds_baseline(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "tool.py", 20)
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    _make_baseline(baseline, total=10)
    failures = check_loc_ratchet(root=tmp_path, baseline_path=baseline)
    assert len(failures) == 1
    assert "rose" in failures[0]
    assert "20 > baseline 10" in failures[0]


def test_red_when_baseline_missing(tmp_path: Path) -> None:
    failures = check_loc_ratchet(root=tmp_path, baseline_path=tmp_path / "missing.txt")
    assert len(failures) == 1
    assert "Baseline file not found" in failures[0]


def test_red_when_baseline_has_no_total(tmp_path: Path) -> None:
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("src/npc_engine: 10\n", encoding="utf-8")
    failures = check_loc_ratchet(root=tmp_path, baseline_path=baseline)
    assert len(failures) == 1
    assert "no 'total:' entry" in failures[0]


def test_moving_loc_between_dirs_is_visible(tmp_path: Path) -> None:
    """LOC moved from src to scripts does not hide a net rise."""
    _write_py(tmp_path / "scripts" / "tool.py", 10)
    _write_py(tmp_path / "src" / "npc_engine" / "mod.py", 10)
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    # Baseline set low to catch any increase
    _make_baseline(baseline, total=15)
    # Total is 20, baseline is 15 → red
    failures = check_loc_ratchet(root=tmp_path, baseline_path=baseline)
    assert len(failures) == 1


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------


def test_main_green_on_current_tree() -> None:
    """The live repo must be within the seeded LOC baseline."""
    rc = main([])
    assert rc == 0


def test_main_red_on_inflated_tree(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "big.py", 100)
    baseline = tmp_path / "scripts" / "loc_baseline.txt"
    _make_baseline(baseline, total=10)
    rc = main(["--root", str(tmp_path)])
    assert rc == 1


def test_main_update_writes_baseline(tmp_path: Path) -> None:
    _write_py(tmp_path / "scripts" / "tool.py", 5)
    baseline_path = tmp_path / "scripts" / "loc_baseline.txt"
    rc = main(["--root", str(tmp_path), "--update"])
    assert rc == 0
    assert baseline_path.exists()
    data = read_baseline(baseline_path)
    assert data["scripts"] == 5
    assert data["total"] == 5
