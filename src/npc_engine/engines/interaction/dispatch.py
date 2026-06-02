"""
Module: dispatch
Layer: engines
Purpose: Routes InteractionProposal to the correct handler for local in-process
         dispatch. Note: the API layer (api/routes/interaction.py) implements the
         full server-side handlers (trade, quest, give_item intercept). This module
         is used for in-process fallback and proposal-kind routing; most demo paths
         go through the HTTP API instead.
Does NOT: write graph state, call LLMs, or issue HTTP requests.
Dependencies injected: None.
Used by: demo_game.game_controller (via dispatch_interaction for proposal routing)
"""

from __future__ import annotations

import logging
from typing import Callable

from npc_engine.engines.interaction.models import (
    UI_DIRECTIVE_STUB,
    STATUS_OPEN,
    InteractionProposal,
    InteractionState,
)


_logger = logging.getLogger(__name__)


def _stub_handler(proposal: InteractionProposal) -> InteractionState:
    """Placeholder handler — logs the proposal and returns an open stub state.

    Args:
        proposal: The incoming interaction proposal.

    Returns:
        InteractionState with status=open and ui_directive=show_stub.
    """
    _logger.info("interaction stub: kind=%s target=%s payload=%s", proposal.kind, proposal.target_id, proposal.payload)
    return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_STUB)


_DISPATCH: dict[str, Callable[[InteractionProposal], InteractionState]] = {
    "propose_trade":    _stub_handler,
    "propose_quest":    _stub_handler,
    "claim_completion": _stub_handler,
    "give_item":        _stub_handler,
}


def dispatch_interaction(proposal: InteractionProposal) -> InteractionState:
    """Route a proposal to its registered handler and return the result.

    Unknown kinds fall through to a no-op state (no log noise for non-proposal
    action types like "speak" that are never routed here).

    Args:
        proposal: Interaction proposal extracted from a dialogue action field.

    Returns:
        InteractionState describing the outcome and which UI to show.
    """
    handler = _DISPATCH.get(proposal.kind)
    if handler is None:
        return InteractionState(status=STATUS_OPEN, ui_directive="none")
    return handler(proposal)
