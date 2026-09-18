"""
test_advance_clock_passes_skip_llm.py - Assert advance_clock respects the injected budget guard.

RED anchor for T7.1 Step 2 (wrong entry-point axis). Finding L13-05, SEV-02.

advance_clock is the recommended game_driven path (ENGINES.md §29-31), yet today it
calls scheduler.advance() with no skip_llm_engines check — the budget guard does not
exist at all in game_driven mode.

Does NOT: open Neo4j, call an LLM, or perform real graph I/O.
Dependencies mocked: get_db_session, get_settings; scheduler built directly with a
pre-exhausted TickBudgetGuard.
"""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session, get_tick_scheduler
from npc_engine.api.routes.world import clock as clock_module
from npc_engine.config import Settings, get_settings
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_budget_guard import TickBudgetGuard
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.world.world_state import WorldState

_WORLD = WorldState()
_SETTINGS = Settings(
    API_KEY_SECRET="local_dev_secret_change_this_2026",
    CLOCK_MODE="game_driven",
)


class _CountingEngine:
    """TickEngine stub that records invocations."""

    def __init__(self) -> None:
        """Initialise call counter."""
        self.call_count: int = 0

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Increment the counter and return empty result."""
        self.call_count += 1
        return {}


def _make_exhausted_guard() -> TickBudgetGuard:
    """Return a TickBudgetGuard with zero remaining budget.

    Timestamps are recorded at the current monotonic time so they survive the
    60-second sliding-window prune that happens inside should_skip_llm().
    """
    guard = TickBudgetGuard(max_per_minute=1)
    guard.record_llm_calls(1, now=time.monotonic())
    return guard


@pytest.mark.asyncio
async def test_advance_clock_skips_llm_engines_when_budget_exhausted() -> None:
    """advance_clock must not run LLM engines when the scheduler's budget guard is exhausted.

    On the current tree this fails because TickScheduler does not accept a budget_guard
    constructor argument — the guard is entirely absent from the game_driven code path.
    After the fix, the scheduler checks should_skip_llm() internally so both the autopilot
    and game_driven paths respect the same ceiling (T7.1 Step 2).
    """
    chapter_engine = _CountingEngine()
    exhausted_guard = _make_exhausted_guard()

    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=AsyncMock(**{"run_tick.return_value": {}}),
        event_handler=AsyncMock(**{"run_tick.return_value": {}}),
        gossip_interval=1,
        event_interval=1,
        chapter_engine=chapter_engine,
        chapter_interval=1,
        budget_guard=exhausted_guard,
        distributed_lease_enabled=False,
    )

    app = FastAPI()
    app.include_router(clock_module.router)
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    app.dependency_overrides[get_tick_scheduler] = lambda: scheduler
    app.dependency_overrides[get_settings] = lambda: _SETTINGS

    with (
        patch(
            "npc_engine.scheduler.tick_scheduler.get_world_state",
            new=AsyncMock(return_value=_WORLD),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.persist_clock_state",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.is_tick_done",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.mark_tick_done",
            new=AsyncMock(),
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/clock/advance",
            json={"delta_ticks": 1, "game_time_seconds": 60},
        )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    assert chapter_engine.call_count == 0, (
        f"chapter engine ran {chapter_engine.call_count} time(s) despite exhausted budget; "
        "advance_clock must respect the scheduler's budget_guard (T7.1 Step 2)"
    )


@pytest.mark.asyncio
async def test_advance_clock_runs_llm_engines_when_budget_available() -> None:
    """advance_clock must run LLM engines normally when the budget guard has capacity."""
    chapter_engine = _CountingEngine()
    fresh_guard = TickBudgetGuard(max_per_minute=10)

    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=AsyncMock(**{"run_tick.return_value": {}}),
        event_handler=AsyncMock(**{"run_tick.return_value": {}}),
        gossip_interval=1,
        event_interval=1,
        chapter_engine=chapter_engine,
        chapter_interval=1,
        budget_guard=fresh_guard,
        distributed_lease_enabled=False,
    )

    app = FastAPI()
    app.include_router(clock_module.router)
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    app.dependency_overrides[get_tick_scheduler] = lambda: scheduler
    app.dependency_overrides[get_settings] = lambda: _SETTINGS

    with (
        patch(
            "npc_engine.scheduler.tick_scheduler.get_world_state",
            new=AsyncMock(return_value=_WORLD),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.persist_clock_state",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.is_tick_done",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.mark_tick_done",
            new=AsyncMock(),
        ),
    ):
        client = TestClient(app)
        response = client.post(
            "/clock/advance",
            json={"delta_ticks": 1, "game_time_seconds": 60},
        )

    assert response.status_code == 200
    assert chapter_engine.call_count == 1, (
        "chapter engine must run when budget is available"
    )
