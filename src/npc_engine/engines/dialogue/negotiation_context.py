"""
Module: negotiation_context
Layer: engines
Purpose: Inject live trade-negotiation state into a dialogue turn's serialized
         context so the NPC's reply is grounded in the active barter session
         (ISSUE-071 / S22.4) instead of contradicting trade reality.
Does NOT: open or mutate a negotiation, price items, or call the graph/LLM.
Dependencies injected: NegotiationSession (read-only), supplied by the caller.
Used by: engines.dialogue.dialogue_handler
"""

from __future__ import annotations

import json

from npc_engine.engines.interaction.negotiation_store import NegotiationSession
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_utils import serialize_json

ACTIVE_NEGOTIATION_KEY = "active_negotiation"
_ACTIVE_NEGOTIATION_PRIORITY = 100


def build_active_negotiation_item(session: NegotiationSession) -> ContextItem:
    """Return a pinned Tier-0 ContextItem summarising the active negotiation.

    Args:
        session: The live negotiation session for this (player, NPC) pair.
    Returns:
        A pinned tier0 ContextItem whose text is the session summary JSON.
    """
    return ContextItem(
        key=ACTIVE_NEGOTIATION_KEY,
        text=serialize_json(session.to_dict(), compact=True),
        tier="tier0",
        priority=_ACTIVE_NEGOTIATION_PRIORITY,
        pinned=True,
    )


def inject_active_negotiation(
    serialized_context: str, session: NegotiationSession | None, npc_id: str
) -> str:
    """Merge the active-negotiation summary into a serialized context string.

    Returns serialized_context unchanged when there is no active session for this
    NPC (no session, or the session's seller is a different NPC) or when the
    context string is not a JSON object. Otherwise the session summary is merged
    under the ``active_negotiation`` key so the NPC's reply reflects live trade
    reality (ISSUE-071).

    Args:
        serialized_context: Compact JSON context string from the context builder.
        session: Active negotiation session for the player, or None.
        npc_id: The NPC the player is currently speaking to.
    Returns:
        The context string with the negotiation summary merged in, or unchanged.
    """
    if session is None or session.seller_id != npc_id:
        return serialized_context
    try:
        context_obj = json.loads(serialized_context)
    except ValueError:
        return serialized_context
    if not isinstance(context_obj, dict):
        return serialized_context
    item = build_active_negotiation_item(session)
    merged = {item.key: json.loads(item.text), **context_obj}
    return serialize_json(merged, compact=True)
