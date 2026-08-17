"""
Unit tests for ISSUE-165: API routes stamp writes with the game clock.

/action previously used int(datetime.now().timestamp()) as a tick, and the
/interaction debt path hardcoded current_tick=0. Both must now read the injected
ClockPort so relation deltas and debt due-dates land on real game ticks.

Does NOT: open Neo4j sessions or call an LLM — the graph writers are patched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session, get_game_clock
from npc_engine.api.routes.dialogue.action import router as action_router
from npc_engine.scheduler.game_clock import GameClock


def _client(clock: GameClock) -> TestClient:
    """Build a test app with the db session and game clock overridden."""
    app = FastAPI()
    app.include_router(action_router, prefix="")
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    app.dependency_overrides[get_game_clock] = lambda: clock
    return TestClient(app)


@pytest.mark.asyncio
async def test_action_route_stamps_the_current_game_tick() -> None:
    """POST /action must pass the clock's tick to apply_relation_delta."""
    clock = GameClock(mode="game_driven")
    await clock.advance(tick_delta=23, time_delta_seconds=0)

    with patch(
        "npc_engine.api.routes.dialogue.action.apply_relation_delta",
        new=AsyncMock(return_value=None),
    ) as mock_apply:
        response = _client(clock).post(
            "/action",
            json={
                "player_id": "player_1",
                "npc_id": "npc_1",
                "action_type": "help",
                "intensity": 5,
            },
        )

    assert response.status_code == 200
    assert mock_apply.await_args.kwargs["tick_id"] == 23


@pytest.mark.asyncio
async def test_action_tick_is_stable_within_one_game_tick() -> None:
    """Two actions at the same game tick must stamp the same tick_id."""
    clock = GameClock(mode="game_driven")
    await clock.advance(tick_delta=4, time_delta_seconds=0)
    client = _client(clock)
    payload = {
        "player_id": "player_1",
        "npc_id": "npc_1",
        "action_type": "help",
        "intensity": 5,
    }

    with patch(
        "npc_engine.api.routes.dialogue.action.apply_relation_delta",
        new=AsyncMock(return_value=None),
    ) as mock_apply:
        client.post("/action", json=payload)
        client.post("/action", json=payload)

    ticks = [call.kwargs["tick_id"] for call in mock_apply.await_args_list]
    assert ticks == [4, 4]
