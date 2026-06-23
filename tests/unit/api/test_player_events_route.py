"""Unit tests for GET /player/{player_id}/events route (EXP-217)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.world.player_events import router


# ---------------------------------------------------------------------------
# Minimal FastAPI test app — auth bypassed; we mock the graph reader directly.
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="")
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_EVENTS = [
    {
        "event_id": "evt_001",
        "event_type": "combat",
        "label": "Battle at the gate",
        "severity": 80,
        "tick_id": 42,
        "location_id": "guard_barracks",
        "src_character_id": "captain_sorn",
    },
    {
        "event_id": "evt_002",
        "event_type": "trade",
        "label": "Market deal",
        "severity": 30,
        "tick_id": 40,
        "location_id": "market_square",
        "src_character_id": "aldric_merchant",
    },
]

_READER_PATH = "npc_engine.api.routes.world.player_events.get_recent_player_events"
_SESSION_PATH = "npc_engine.api.routes.world.player_events.get_db_session"


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_player_events_returns_events_list() -> None:
    """Route returns 200 with a typed list of event rows."""
    mock_session = AsyncMock()

    with patch(_READER_PATH, new=AsyncMock(return_value=_SAMPLE_EVENTS)):
        from npc_engine.api.routes.world.player_events import list_player_events

        result = await list_player_events(
            player_id="player_1",
            limit=20,
            session=mock_session,
        )

    assert result["success"] is True
    events = result["data"]["events"]
    assert len(events) == 2
    assert events[0]["event_id"] == "evt_001"
    assert events[1]["event_id"] == "evt_002"


@pytest.mark.asyncio
async def test_player_events_empty_returns_empty_list() -> None:
    """Route returns 200 with an empty list when the player has no observable events."""
    mock_session = AsyncMock()

    with patch(_READER_PATH, new=AsyncMock(return_value=[])):
        from npc_engine.api.routes.world.player_events import list_player_events

        result = await list_player_events(
            player_id="player_new",
            limit=20,
            session=mock_session,
        )

    assert result["success"] is True
    assert result["data"]["events"] == []


# ---------------------------------------------------------------------------
# limit capping / validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_player_events_reader_called_with_capped_limit() -> None:
    """Reader is called with the limit supplied by the caller (cap enforced by Query)."""
    mock_session = AsyncMock()
    mock_reader = AsyncMock(return_value=[])

    with patch(_READER_PATH, new=mock_reader):
        from npc_engine.api.routes.world.player_events import list_player_events

        await list_player_events(
            player_id="player_1",
            limit=10,
            session=mock_session,
        )

    mock_reader.assert_awaited_once_with(mock_session, player_id="player_1", limit=10)


# ---------------------------------------------------------------------------
# TestClient smoke-tests (verifies route registers and responds correctly)
# ---------------------------------------------------------------------------


def test_route_returns_200_via_test_client() -> None:
    """TestClient smoke-test: route registers and returns 200."""
    app = _make_app()
    mock_session = AsyncMock()

    with patch(_SESSION_PATH, return_value=mock_session), patch(
        _READER_PATH, new=AsyncMock(return_value=_SAMPLE_EVENTS)
    ):
        client = TestClient(app)
        response = client.get("/player/player_1/events")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]["events"]) == 2


def test_route_empty_returns_200_via_test_client() -> None:
    """TestClient smoke-test: empty result returns 200 with empty list."""
    app = _make_app()
    mock_session = AsyncMock()

    with patch(_SESSION_PATH, return_value=mock_session), patch(
        _READER_PATH, new=AsyncMock(return_value=[])
    ):
        client = TestClient(app)
        response = client.get("/player/player_ghost/events")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["events"] == []
