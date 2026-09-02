"""
Module: tests.unit.api.test_dialogue_retrieval_profile
Layer: test (unit)
Purpose: The per-request retrieval-profile switch, end to end at the API boundary —
         the field exists, it reaches the context builder unchanged, and an undeclared
         name is a 4xx rather than a silent fall back to the default.
Dependencies: pytest, fastapi.testclient; npc_engine.api, dialogue models, errors
Used by: make test (pytest discovery)

Why the 4xx matters more than the happy path. If an unknown profile silently resolved to
the default, a generation run would record `retrieval_profile="aggressive"` in its meta.json
while having actually produced default-profile text. The A/B comparison would then be a
confident number attached to the wrong label — a run claiming to measure something it never
measured, which is the failure mode the whole eval programme exists to prevent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session, get_dialogue_handler
from npc_engine.api.routes.dialogue import dialogue
from npc_engine.config import Settings
from npc_engine.engines.dialogue.dialogue_models import DialogueRequest
from npc_engine.utils.errors import RetrievalProfileNotFoundError

_AUTH_SECRET = "local_dev_secret_change_this_2026"
_AUTH_HEADER = {"Authorization": f"Bearer {_AUTH_SECRET}"}
_ROUTE_MOD = "npc_engine.api.routes.dialogue.dialogue"


def test_dialogue_request_accepts_a_retrieval_profile() -> None:
    req = DialogueRequest(
        player_id="p1", npc_id="npc_1", player_message="hi", retrieval_profile="aggressive"
    )

    assert req.retrieval_profile == "aggressive"


def test_retrieval_profile_defaults_to_none_so_existing_clients_are_unaffected() -> None:
    """The field is additive: every caller that predates it keeps working, and None means
    'use the deployment default', not 'no profile'."""
    req = DialogueRequest(player_id="p1", npc_id="npc_1", player_message="hi")

    assert req.retrieval_profile is None


def test_handler_forwards_the_request_profile_to_the_context_adapter() -> None:
    """The value must survive the whole chain. A field the API accepts and then drops
    would produce arms that differ only in their label.

    Asserted against the real call site in _build_dialogue_prompt: constructing a
    DialogueHandler needs eight collaborators, and a spy over a hand-built handler would
    test the spy rather than the wiring.
    """
    from pathlib import Path

    # Anchored on __file__, not cwd: the bare relative path only resolved when
    # pytest happened to run from the repo root (R3.4d).
    repo_root = Path(__file__).resolve().parents[3]
    source = (repo_root / "src/npc_engine/engines/dialogue/dialogue_handler.py").read_text(encoding="utf-8")

    assert "retrieval_profile=request.retrieval_profile," in source, (
        "the handler must forward the request's profile to build_context"
    )


def test_context_adapter_accepts_the_profile_keyword() -> None:
    """Signature contract: the adapter is the seam between the engine and retrieval."""
    import inspect

    from npc_engine.retrieval.dialogue_context.dialogue_context_adapter import (
        Neo4jDialogueContextAdapter,
    )

    params = inspect.signature(Neo4jDialogueContextAdapter.build_context).parameters

    assert "retrieval_profile" in params


def _build_dialogue_app(handler: object) -> FastAPI:
    """Mount the dialogue router with the handler and session stubbed out.

    Auth middleware is omitted deliberately: this exercises the route's exception
    mapping, not the auth chain, which test_dialogue_pending_route.py covers.
    """
    app = FastAPI()
    app.include_router(dialogue.router, prefix="/v1")

    async def _db_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_stub
    app.dependency_overrides[dialogue.get_settings] = lambda: Settings(API_KEY_SECRET=_AUTH_SECRET)
    app.dependency_overrides[get_dialogue_handler] = lambda: handler
    return app


def test_route_maps_an_unknown_profile_to_400() -> None:
    """An undeclared profile is a 400 the caller can act on, not a silent default.

    Replaces a static source-substring check that could not fail meaningfully:
    it asserted "RetrievalProfileNotFoundError" and "RETRIEVAL_PROFILE_NOT_FOUND"
    appeared somewhere in dialogue.py, but the first also appears in the import on
    line 25, so deleting the except clause left the test green. Verified: with the
    except clause removed this test reds and the old one did not (R3.4d).

    The path only became reachable in R3.1. Until the degradation ladder stopped
    swallowing everything, this error was raised inside build_context, caught
    twice, and served as a canned HTTP 200.
    """
    handler = AsyncMock()
    handler.handle.side_effect = RetrievalProfileNotFoundError(
        requested="aggressive", available="default, conservative"
    )

    with patch(f"{_ROUTE_MOD}.resolve_system_state", new=AsyncMock(return_value=None)):
        client = TestClient(_build_dialogue_app(handler))
        response = client.post(
            "/v1/dialogue",
            json={"player_id": "p1", "npc_id": "npc_1", "player_message": "hi",
                  "retrieval_profile": "aggressive"},
            headers=_AUTH_HEADER,
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "RETRIEVAL_PROFILE_NOT_FOUND"


def test_unknown_profile_response_names_the_available_profiles() -> None:
    """A bare 400 cannot tell a typo from a missing config file.

    Profile names are deployment configuration the caller is entitled to know,
    unlike the node id redacted on the 422 path.
    """
    handler = AsyncMock()
    handler.handle.side_effect = RetrievalProfileNotFoundError(
        requested="aggressive", available="default, conservative"
    )

    with patch(f"{_ROUTE_MOD}.resolve_system_state", new=AsyncMock(return_value=None)):
        client = TestClient(_build_dialogue_app(handler))
        response = client.post(
            "/v1/dialogue",
            json={"player_id": "p1", "npc_id": "npc_1", "player_message": "hi",
                  "retrieval_profile": "aggressive"},
            headers=_AUTH_HEADER,
        )

    message = response.json()["detail"]["message"]
    assert "aggressive" in message
    assert "conservative" in message


def test_the_error_names_what_was_asked_for_and_what_exists() -> None:
    """A 4xx that does not say which names are valid makes the harness undebuggable."""
    err = RetrievalProfileNotFoundError(requested="aggresive", available="default, aggressive")

    assert "aggresive" in str(err)
    assert "aggressive" in str(err)
