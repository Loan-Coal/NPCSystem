"""
Module: test_guard_pairing_unit
Layer: tests (unit)
Purpose: Pin RECORDED_GUARD_N as a COUNT OF CASES (ISSUE-254). The number equals the
         stale guard_turns the broken join reported, so it invites a "fix" to 234.
         Repetitions of one case are not independent observations.
Dependencies: pytest; mde, summary (evals/)
Used by: `make test`, `make check` via test-cov-evals.
"""

from __future__ import annotations

from pathlib import Path

from mde import KAPPA_GENERATION, RECORDED_GUARD_N
from summary import summarize_from_dir

REPO_ROOT = Path(__file__).resolve().parents[3]
_CURRENT_GEN = REPO_ROOT / "evals" / "generations" / "k3_77688e7_regen1"


def test_recorded_guard_n_is_a_case_count_not_a_turn_count() -> None:
    """78 is guard_cases. guard_turns is 234 at k=3, and is NOT the pairing unit."""
    summary = summarize_from_dir(_CURRENT_GEN)
    assert RECORDED_GUARD_N == summary.guard_cases
    assert RECORDED_GUARD_N != summary.guard_turns
    assert summary.guard_turns > summary.guard_cases


def test_the_kappa_generation_is_named_not_implied() -> None:
    """Both recorded measurements point at one named corpus, so they cannot drift apart."""
    assert KAPPA_GENERATION
    assert (REPO_ROOT / "evals" / "generations" / KAPPA_GENERATION).is_dir()
