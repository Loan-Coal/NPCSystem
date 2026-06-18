"""
test_dialogue_negotiation_context.py - Unit tests for the active-negotiation context inject.

S22.4 (ISSUE-071): during a live barter loop the NPC's dialogue context must carry the
negotiation state so the reply does not contradict trade reality. Covers the injection
path (active session for this NPC) and the no-active-session path.

Does NOT: touch Neo4j, the LLM, or build a full DialogueHandler.
"""

from __future__ import annotations

import json

from npc_engine.engines.dialogue.negotiation_context import (
    ACTIVE_NEGOTIATION_KEY,
    build_active_negotiation_item,
    inject_active_negotiation,
)
from npc_engine.engines.interaction.negotiation_store import NegotiationSession

_BASE_CONTEXT = json.dumps({"world": {"epoch": "war"}, "npc": {"profile": {}}})


def _session(*, seller_id: str = "mira_innkeeper", threshold: int = 27) -> NegotiationSession:
    return NegotiationSession(
        item_id="itm_ale",
        item_type="drink",
        seller_id=seller_id,
        center_price=30,
        threshold=threshold,
        current_offer=25,
        moves=(),
        status="open",
        accumulated_band=0.0,
    )


def test_inject_adds_active_negotiation_for_matching_npc() -> None:
    """A session whose seller is the NPC is merged under the active_negotiation key."""
    out = inject_active_negotiation(_BASE_CONTEXT, _session(), npc_id="mira_innkeeper")

    obj = json.loads(out)
    assert ACTIVE_NEGOTIATION_KEY in obj
    assert obj[ACTIVE_NEGOTIATION_KEY]["threshold"] == 27
    assert obj[ACTIVE_NEGOTIATION_KEY]["seller_id"] == "mira_innkeeper"
    # Existing context is preserved.
    assert obj["world"]["epoch"] == "war"


def test_inject_noop_when_no_session() -> None:
    """No active session leaves the context untouched."""
    out = inject_active_negotiation(_BASE_CONTEXT, None, npc_id="mira_innkeeper")
    assert out == _BASE_CONTEXT


def test_inject_noop_when_session_belongs_to_other_npc() -> None:
    """A session for a different NPC must not leak into this NPC's context."""
    out = inject_active_negotiation(
        _BASE_CONTEXT, _session(seller_id="aldric_merchant"), npc_id="mira_innkeeper"
    )
    assert out == _BASE_CONTEXT
    assert ACTIVE_NEGOTIATION_KEY not in json.loads(out)


def test_inject_noop_when_context_not_json_object() -> None:
    """Malformed or non-object context is returned unchanged (fail-safe)."""
    assert inject_active_negotiation("not-json{{", _session(), "mira_innkeeper") == "not-json{{"
    assert inject_active_negotiation("[1, 2]", _session(), "mira_innkeeper") == "[1, 2]"


def test_build_item_is_pinned_tier0() -> None:
    """The negotiation context item is pinned Tier-0 with the summary as text."""
    item = build_active_negotiation_item(_session())
    assert item.key == ACTIVE_NEGOTIATION_KEY
    assert item.tier == "tier0"
    assert item.pinned is True
    assert json.loads(item.text)["item_id"] == "itm_ale"
