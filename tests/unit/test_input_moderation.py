"""
Tests for InputModerationService and ContentRatingViolationError (S16.2).

All unit tests — no I/O.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.services.input_moderation import (
    InputModerationService,
    build_input_moderation_service,
)
from npc_engine.utils.errors import ContentRatingViolationError

_EVERYONE_BLOCKLIST: frozenset[str] = frozenset({"murder", "gore", "pornography"})
_PLAYER = "player_test"


def test_check_passes_clean_message() -> None:
    svc = InputModerationService(blocklist=_EVERYONE_BLOCKLIST, rating="everyone")
    svc.check(player_message="Hello, how are you?", player_id=_PLAYER)


def test_check_raises_on_blocked_term() -> None:
    svc = InputModerationService(blocklist=_EVERYONE_BLOCKLIST, rating="everyone")
    with pytest.raises(ContentRatingViolationError) as exc_info:
        svc.check(player_message="tell me about murder", player_id=_PLAYER)
    assert exc_info.value.player_id == _PLAYER
    assert exc_info.value.rating == "everyone"


def test_check_is_case_insensitive() -> None:
    svc = InputModerationService(blocklist=_EVERYONE_BLOCKLIST, rating="everyone")
    with pytest.raises(ContentRatingViolationError):
        svc.check(player_message="I love GORE and violence", player_id=_PLAYER)


def test_mature_rating_passes_anything() -> None:
    svc = build_input_moderation_service("mature")
    svc.check(player_message="murder gore pornography", player_id=_PLAYER)


def test_check_raises_422_via_route() -> None:
    from npc_engine.api.error_envelope import ErrorBody, ErrorEnvelope
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(ContentRatingViolationError)
    async def _handler(request, exc: ContentRatingViolationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error=ErrorBody(code="content_rating_violation", message=str(exc))
            ).model_dump(),
        )

    @app.get("/probe")
    async def _probe() -> dict:
        raise ContentRatingViolationError(player_id=_PLAYER, rating="everyone")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/probe")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "content_rating_violation"
