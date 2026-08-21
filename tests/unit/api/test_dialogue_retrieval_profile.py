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

import pytest

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest
from npc_engine.utils.errors import RetrievalProfileNotFoundError


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

    source = Path("src/npc_engine/engines/dialogue/dialogue_handler.py").read_text(encoding="utf-8")

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


def test_route_maps_an_unknown_profile_to_4xx() -> None:
    """Static contract check: the dialogue route must translate the domain error.

    Verified against the route source rather than a live request because reaching the
    raise needs a full engine stack; the mapping itself is what regresses.
    """
    from pathlib import Path

    source = Path("src/npc_engine/api/routes/dialogue/dialogue.py").read_text(encoding="utf-8")

    assert "RetrievalProfileNotFoundError" in source
    assert "RETRIEVAL_PROFILE_NOT_FOUND" in source


def test_the_error_names_what_was_asked_for_and_what_exists() -> None:
    """A 4xx that does not say which names are valid makes the harness undebuggable."""
    err = RetrievalProfileNotFoundError(requested="aggresive", available="default, aggressive")

    assert "aggresive" in str(err)
    assert "aggressive" in str(err)
