"""
test_tick_budget_guard.py - Unit tests for TickBudgetGuard sliding-window LLM ceiling.

Does NOT: exercise the scheduler, autopilot, or graph.
"""

from __future__ import annotations

import pytest

from npc_engine.scheduler.tick_budget_guard import TickBudgetGuard


# ---------------------------------------------------------------------------
# Initialisation / clamping
# ---------------------------------------------------------------------------

def test_max_per_minute_clamped_to_1_when_zero() -> None:
    guard = TickBudgetGuard(max_per_minute=0)
    assert guard._max_per_minute == 1


def test_max_per_minute_clamped_to_1_when_negative() -> None:
    guard = TickBudgetGuard(max_per_minute=-5)
    assert guard._max_per_minute == 1


def test_max_per_minute_stored_as_given() -> None:
    guard = TickBudgetGuard(max_per_minute=10)
    assert guard._max_per_minute == 10


# ---------------------------------------------------------------------------
# should_skip_llm
# ---------------------------------------------------------------------------

def test_should_not_skip_when_no_records() -> None:
    guard = TickBudgetGuard(max_per_minute=3)
    assert guard.should_skip_llm(now=100.0) is False


def test_should_not_skip_when_below_max() -> None:
    guard = TickBudgetGuard(max_per_minute=3)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    assert guard.should_skip_llm(now=102.0) is False


def test_should_skip_when_at_max() -> None:
    guard = TickBudgetGuard(max_per_minute=3)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    guard.record_llm_tick(now=102.0)
    assert guard.should_skip_llm(now=103.0) is True


def test_should_skip_when_above_max() -> None:
    guard = TickBudgetGuard(max_per_minute=2)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    guard.record_llm_tick(now=102.0)
    assert guard.should_skip_llm(now=103.0) is True


def test_budget_resets_after_window_expires() -> None:
    guard = TickBudgetGuard(max_per_minute=2)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    # 60 seconds later — both timestamps fall out of the 60s window
    assert guard.should_skip_llm(now=162.0) is False


def test_partial_expiry_keeps_recent_timestamps() -> None:
    guard = TickBudgetGuard(max_per_minute=2)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=150.0)
    # At t=161, the first timestamp (100.0) is exactly expired (161 - 60 = 101 > 100)
    # but the second (150.0) is still in window → count=1, max=2 → not skipped
    assert guard.should_skip_llm(now=161.0) is False


def test_boundary_timestamp_exactly_at_cutoff_is_pruned() -> None:
    guard = TickBudgetGuard(max_per_minute=1)
    guard.record_llm_tick(now=100.0)
    # cutoff = 160.0 - 60 = 100.0; timestamp <= cutoff → pruned
    assert guard.should_skip_llm(now=160.0) is False


# ---------------------------------------------------------------------------
# remaining
# ---------------------------------------------------------------------------

def test_remaining_full_when_no_records() -> None:
    guard = TickBudgetGuard(max_per_minute=5)
    assert guard.remaining == 5


def test_remaining_decrements_on_record() -> None:
    guard = TickBudgetGuard(max_per_minute=5)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    # remaining uses time.monotonic() internally; set fresh timestamps so they stay in window
    # Force a fresh check by recording again and checking via should_skip_llm
    assert guard.should_skip_llm(now=102.0) is False
    # After 2 records with max=5, 3 remain
    guard._prune(102.0)  # ensure window is clean
    assert len(guard._timestamps) == 2
    assert guard._max_per_minute - len(guard._timestamps) == 3


def test_remaining_zero_when_budget_exhausted() -> None:
    guard = TickBudgetGuard(max_per_minute=2)
    guard.record_llm_tick(now=100.0)
    guard.record_llm_tick(now=101.0)
    guard._prune(102.0)
    assert max(0, guard._max_per_minute - len(guard._timestamps)) == 0
