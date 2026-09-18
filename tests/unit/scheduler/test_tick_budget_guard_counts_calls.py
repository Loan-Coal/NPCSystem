"""
test_tick_budget_guard_counts_calls.py - Assert TickBudgetGuard counts per backend call, not per tick.

RED anchor for T7.1 Step 3. Finding L13-05, SEV-02.

Does NOT: open Neo4j, call an LLM, or perform real I/O.
"""
from __future__ import annotations

import pytest

from npc_engine.scheduler.tick_budget_guard import TickBudgetGuard


def test_record_llm_calls_consumes_n_budget_slots() -> None:
    """Recording N LLM calls must consume N budget slots, not 1.

    Before the fix, only record_llm_tick() exists and records 1 timestamp per
    call, so two ticks of 3 calls each consume 2 slots against a max of 5 and
    should_skip_llm() returns False. After the fix, record_llm_calls(3) records
    3 timestamps per call, so 3+3=6 calls exhaust the max-5 guard.
    """
    guard = TickBudgetGuard(max_per_minute=5)
    now = 0.0
    guard.record_llm_calls(3, now=now)
    guard.record_llm_calls(3, now=now)
    assert guard.should_skip_llm(now=now), (
        "After recording 6 LLM calls against a max of 5, should_skip_llm() must return True. "
        "record_llm_tick() records only 1 per invocation — that is the bug (T7.1 Step 3)."
    )


def test_record_llm_calls_zero_does_not_consume_budget() -> None:
    """Recording zero calls must not consume any budget slot."""
    guard = TickBudgetGuard(max_per_minute=1)
    now = 0.0
    guard.record_llm_calls(0, now=now)
    assert not guard.should_skip_llm(now=now)


def test_record_llm_calls_single_is_equivalent_to_record_llm_tick() -> None:
    """record_llm_calls(1) and record_llm_tick() must behave identically."""
    g1 = TickBudgetGuard(max_per_minute=2)
    g2 = TickBudgetGuard(max_per_minute=2)
    now = 0.0
    g1.record_llm_calls(1, now=now)
    g2.record_llm_tick(now=now)
    assert g1.should_skip_llm(now=now) == g2.should_skip_llm(now=now)
    assert g1.remaining == g2.remaining


def test_record_llm_calls_respects_window_expiry() -> None:
    """Calls recorded outside the 60-second window must not count toward the budget."""
    guard = TickBudgetGuard(max_per_minute=3)
    guard.record_llm_calls(3, now=0.0)
    assert guard.should_skip_llm(now=0.0)
    assert not guard.should_skip_llm(now=61.0), (
        "Calls older than 60 s must expire from the sliding window."
    )
