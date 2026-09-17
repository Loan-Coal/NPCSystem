"""
test_clock_advance_delta_bound.py - Guards the MAX_DELTA_TICKS cap on clock advances.

Advancing by 1000 ticks holds the scheduler lock for ~8 minutes (433-570 ms/tick
deterministic floor).  MAX_DELTA_TICKS must be a single-digit ceiling to avoid this.

Does NOT: open Neo4j, call an LLM, or read real settings.
Dependencies injected: FastAPI dependency overrides; stub scheduler.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session, get_tick_scheduler
from npc_engine.api.routes.world import clock
from npc_engine.config import Settings, get_settings

# Hardcoded boundary values — NOT imported from config, so that changing the cap
# makes this test go red rather than silently tracking the change.
_NEW_CAP: int = 10
_OVER_NEW_CAP: int = 11
_AT_NEW_CAP: int = 10


def _make_client() -> TestClient:
    """Build a minimal FastAPI test app wired to the clock advance route."""

    class _StubScheduler:
        async def advance(self, **kwargs: Any) -> dict[str, Any]:
            return {"clock": {}, "gossip": [], "event": []}

    app = FastAPI()
    app.include_router(clock.router)
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    app.dependency_overrides[get_tick_scheduler] = lambda: _StubScheduler()
    app.dependency_overrides[get_settings] = lambda: Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        CLOCK_MODE="game_driven",
    )
    return TestClient(app)


def test_delta_ticks_above_cap_is_rejected_with_422() -> None:
    """Pydantic must reject delta_ticks=11 before the route handler runs.

    Failing today: MAX_DELTA_TICKS is 1000, so delta_ticks=11 passes the
    field validator and the route returns 200.  After the fix the cap is 10
    and the request is rejected with 422.
    """
    response = _make_client().post(
        "/clock/advance", json={"delta_ticks": _OVER_NEW_CAP, "game_time_seconds": 1}
    )
    assert response.status_code == 422, (
        f"Expected 422 for delta_ticks={_OVER_NEW_CAP} (cap should be {_NEW_CAP}), "
        f"got {response.status_code} — MAX_DELTA_TICKS may still be 1000"
    )


def test_delta_ticks_at_cap_is_accepted() -> None:
    """delta_ticks=10 (the boundary value after the fix) must be accepted with 200."""
    response = _make_client().post(
        "/clock/advance", json={"delta_ticks": _AT_NEW_CAP, "game_time_seconds": 1}
    )
    assert response.status_code == 200, (
        f"Expected 200 for delta_ticks={_AT_NEW_CAP}, got {response.status_code}"
    )
