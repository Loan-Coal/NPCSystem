"""
test_tick_autopilot.py - Unit tests for TickAutopilot background driver.

Does NOT: exercise Neo4j or TickScheduler internals.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.scheduler.tick_autopilot import TickAutopilot
from npc_engine.scheduler.tick_budget_guard import TickBudgetGuard


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _make_graph_db(session_stub=None):
    """Return a minimal graph_db stub whose get_session() yields session_stub."""
    db = MagicMock()
    db.get_session = _make_session_ctx(session_stub or AsyncMock())
    return db


def _make_session_ctx(session):
    """Return a zero-arg function that returns an async context manager yielding session."""
    @asynccontextmanager
    async def _ctx():
        yield session
    return _ctx


def _make_scheduler(tick_id: int = 1) -> MagicMock:
    scheduler = MagicMock()
    scheduler.advance = AsyncMock(return_value={
        "clock": {"tick_id": tick_id},
        "gossip": [],
        "event": [],
    })
    return scheduler


# ---------------------------------------------------------------------------
# advance_once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advance_once_calls_scheduler_with_tick_delta_1() -> None:
    scheduler = _make_scheduler()
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=5,
    )
    await autopilot.advance_once()
    scheduler.advance.assert_awaited_once()
    _, kwargs = scheduler.advance.call_args
    assert kwargs["tick_delta"] == 1
    assert kwargs["time_delta_seconds"] == 5


@pytest.mark.asyncio
async def test_advance_once_returns_scheduler_result() -> None:
    scheduler = _make_scheduler(tick_id=42)
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
    )
    result = await autopilot.advance_once()
    assert result["clock"]["tick_id"] == 42


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------

def test_interval_clamped_to_minimum_1() -> None:
    ap = TickAutopilot(
        graph_db=MagicMock(),
        tick_scheduler=MagicMock(),
        interval_seconds=0,
        game_seconds_per_tick=1,
    )
    assert ap._interval_seconds == 1


def test_game_seconds_clamped_to_minimum_0() -> None:
    ap = TickAutopilot(
        graph_db=MagicMock(),
        tick_scheduler=MagicMock(),
        interval_seconds=10,
        game_seconds_per_tick=-5,
    )
    assert ap._game_seconds_per_tick == 0


# ---------------------------------------------------------------------------
# run_forever
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_forever_calls_advance_once_per_loop() -> None:
    scheduler = _make_scheduler()
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
    )

    call_count = 0
    original_advance = autopilot.advance_once

    async def _counting_advance():
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            raise asyncio.CancelledError
        return await original_advance()

    autopilot.advance_once = _counting_advance  # type: ignore[method-assign]

    with patch("npc_engine.scheduler.tick_autopilot.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(asyncio.CancelledError):
            await autopilot.run_forever()

    assert call_count == 3


@pytest.mark.asyncio
async def test_run_forever_propagates_cancelled_error() -> None:
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=_make_scheduler(),
        interval_seconds=1,
        game_seconds_per_tick=1,
    )

    async def _raise_cancel():
        raise asyncio.CancelledError

    autopilot.advance_once = _raise_cancel  # type: ignore[method-assign]

    with patch("npc_engine.scheduler.tick_autopilot.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(asyncio.CancelledError):
            await autopilot.run_forever()


@pytest.mark.asyncio
async def test_run_forever_swallows_non_cancellation_exception_and_continues() -> None:
    """A transient error must not kill the loop; the next iteration must proceed."""
    scheduler = _make_scheduler()
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=1,
        game_seconds_per_tick=1,
    )

    call_count = 0

    async def _flaky_advance():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient DB error")
        if call_count >= 2:
            raise asyncio.CancelledError
        return {"clock": {"tick_id": 1}, "gossip": [], "event": []}

    autopilot.advance_once = _flaky_advance  # type: ignore[method-assign]

    with patch("npc_engine.scheduler.tick_autopilot.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(asyncio.CancelledError):
            await autopilot.run_forever()

    assert call_count == 2


@pytest.mark.asyncio
async def test_run_forever_sleeps_between_advances() -> None:
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=_make_scheduler(),
        interval_seconds=7,
        game_seconds_per_tick=1,
    )

    sleep_calls: list[int] = []
    advance_count = 0

    async def _fake_advance():
        nonlocal advance_count
        advance_count += 1
        if advance_count >= 2:
            raise asyncio.CancelledError
        return {"clock": {"tick_id": 1}, "gossip": [], "event": []}

    autopilot.advance_once = _fake_advance  # type: ignore[method-assign]

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(int(seconds))

    with patch("npc_engine.scheduler.tick_autopilot.asyncio.sleep", side_effect=_fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await autopilot.run_forever()

    assert sleep_calls == [7]


# ---------------------------------------------------------------------------
# Budget guard integration in advance_once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advance_once_passes_skip_llm_false_when_budget_available() -> None:
    scheduler = _make_scheduler()
    guard = TickBudgetGuard(max_per_minute=5)
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
        budget_guard=guard,
    )
    await autopilot.advance_once()
    _, kwargs = scheduler.advance.call_args
    assert kwargs["skip_llm_engines"] is False


@pytest.mark.asyncio
async def test_advance_once_passes_skip_llm_true_when_budget_exhausted() -> None:
    scheduler = _make_scheduler()
    guard = TickBudgetGuard(max_per_minute=1)
    now = 100.0
    guard.record_llm_tick(now=now)  # exhaust the budget
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
        budget_guard=guard,
    )
    # Patch should_skip_llm to return True deterministically
    guard._timestamps.clear()
    guard.record_llm_tick(now=now)
    # Force the guard to see budget exhausted at current time (use a large now in should_skip check)
    original_should_skip = guard.should_skip_llm

    def _forced_skip(**kwargs):
        return True

    guard.should_skip_llm = _forced_skip  # type: ignore[method-assign]

    await autopilot.advance_once()
    _, kwargs = scheduler.advance.call_args
    assert kwargs["skip_llm_engines"] is True


@pytest.mark.asyncio
async def test_advance_once_records_llm_tick_when_not_skipped() -> None:
    scheduler = _make_scheduler()
    guard = TickBudgetGuard(max_per_minute=5)
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
        budget_guard=guard,
    )
    assert len(guard._timestamps) == 0
    await autopilot.advance_once()
    assert len(guard._timestamps) == 1


@pytest.mark.asyncio
async def test_advance_once_does_not_record_when_budget_skipped() -> None:
    scheduler = _make_scheduler()
    guard = TickBudgetGuard(max_per_minute=5)

    def _forced_skip(**kwargs):
        return True

    guard.should_skip_llm = _forced_skip  # type: ignore[method-assign]

    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
        budget_guard=guard,
    )
    await autopilot.advance_once()
    assert len(guard._timestamps) == 0


@pytest.mark.asyncio
async def test_advance_once_no_budget_guard_does_not_skip() -> None:
    scheduler = _make_scheduler()
    autopilot = TickAutopilot(
        graph_db=_make_graph_db(),
        tick_scheduler=scheduler,
        interval_seconds=10,
        game_seconds_per_tick=1,
        budget_guard=None,
    )
    await autopilot.advance_once()
    _, kwargs = scheduler.advance.call_args
    assert kwargs["skip_llm_engines"] is False
