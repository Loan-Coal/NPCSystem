"""Unit tests for GET /v1/dialogue/pending (Phase 14 S14.3)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.routes.dialogue import dialogue
from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.common.intent_models import ConversationIntent
from npc_engine.config import Settings

_AUTH_SECRET = "local_dev_secret_change_this_2026"
_AUTH_HEADER = {"Authorization": f"Bearer {_AUTH_SECRET}"}

_INTENT_A = ConversationIntent(
    npc_id="captain_sorn",
    player_id="player1",
    tick=5,
    score=0.9,
    reason="I need help with hunger",
    trigger_type="need",
    trigger_ref="need-food",
)
_INTENT_B = ConversationIntent(
    npc_id="mira_innkeeper",
    player_id="player1",
    tick=5,
    score=0.7,
    reason="Did you hear about Northern war begins",
    trigger_type="event",
    trigger_ref="evt-war",
)

_ROUTE_MOD = "npc_engine.api.routes.dialogue.dialogue"


def _settings() -> Settings:
    return Settings(API_KEY_SECRET=_AUTH_SECRET)


def _build_app(*, with_auth: bool = False) -> FastAPI:
    app = FastAPI()
    if with_auth:
        app.add_middleware(ApiKeyMiddleware, settings=_settings(), idempotency_service=None)
    app.include_router(dialogue.router, prefix="/v1")

    async def _db_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_stub
    app.dependency_overrides[dialogue.get_settings] = _settings
    return app


# ---------------------------------------------------------------------------
# 200 paths
# ---------------------------------------------------------------------------


def test_returns_200_with_intents():
    """Returns a list of ConversationIntentResponse when intents are pending."""
    with (
        patch(f"{_ROUTE_MOD}.get_pending_intents_from_queue", new=AsyncMock(return_value=[_INTENT_A, _INTENT_B])),
        patch(f"{_ROUTE_MOD}.mark_intent_delivered", new=AsyncMock()),
    ):
        client = TestClient(_build_app())
        response = client.get("/v1/dialogue/pending", params={"player_id": "player1"}, headers=_AUTH_HEADER)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["npc_id"] == "captain_sorn"
    assert body[0]["trigger_type"] == "need"


def test_returns_200_empty_list():
    """Returns [] when no pending intents exist."""
    with (
        patch(f"{_ROUTE_MOD}.get_pending_intents_from_queue", new=AsyncMock(return_value=[])),
        patch(f"{_ROUTE_MOD}.mark_intent_delivered", new=AsyncMock()),
    ):
        client = TestClient(_build_app())
        response = client.get("/v1/dialogue/pending", params={"player_id": "player1"}, headers=_AUTH_HEADER)

    assert response.status_code == 200
    assert response.json() == []


def test_marks_delivered_after_fetch():
    """mark_intent_delivered is called once per returned intent."""
    with (
        patch(f"{_ROUTE_MOD}.get_pending_intents_from_queue", new=AsyncMock(return_value=[_INTENT_A, _INTENT_B])),
        patch(f"{_ROUTE_MOD}.mark_intent_delivered", new=AsyncMock()) as mock_mark,
    ):
        client = TestClient(_build_app())
        client.get("/v1/dialogue/pending", params={"player_id": "player1"}, headers=_AUTH_HEADER)

    assert mock_mark.call_count == 2


# ---------------------------------------------------------------------------
# 401 path
# ---------------------------------------------------------------------------


def test_returns_401_without_auth_header():
    """Missing Authorization header yields 401 from the auth middleware."""
    with (
        patch(f"{_ROUTE_MOD}.get_pending_intents_from_queue", new=AsyncMock(return_value=[])),
        patch(f"{_ROUTE_MOD}.mark_intent_delivered", new=AsyncMock()),
    ):
        client = TestClient(_build_app(with_auth=True))
        response = client.get("/v1/dialogue/pending", params={"player_id": "player1"})

    assert response.status_code == 401
