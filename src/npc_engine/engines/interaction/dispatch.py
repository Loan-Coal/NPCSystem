"""
Module: dispatch
Layer: engines
Purpose: Routes InteractionProposal to the correct handler for local in-process
         dispatch. Note: the API layer (api/routes/interaction.py) implements the
         full server-side handlers (trade, quest, give_item intercept). This module
         is used for in-process fallback and proposal-kind routing; most demo paths
         go through the HTTP API instead.
Does NOT: write graph state, call LLMs, or issue HTTP requests.
Dependencies injected: SyncTradeHandlerProtocol via set_trade_handler (default:
         MinimalSyncTradeHandler). propose_quest and claim_completion remain stubs.
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
from npc_engine.engines.interaction.trade_handler_sync import (
    MinimalSyncTradeHandler,
    SyncTradeHandlerProtocol,
)


_logger = logging.getLogger(__name__)

_trade_handler: SyncTradeHandlerProtocol = MinimalSyncTradeHandler()


def set_trade_handler(handler: SyncTradeHandlerProtocol) -> None:
    """Replace the module-level trade handler (test seam / production injection).

    Args:
        handler: Any object satisfying SyncTradeHandlerProtocol.
    """
    global _trade_handler
    _trade_handler = handler


def _stub_handler(proposal: InteractionProposal) -> InteractionState:
    """Placeholder handler — logs the proposal and returns an open stub state.

    Args:
        proposal: The incoming interaction proposal.

    Returns:
        InteractionState with status=open and ui_directive=show_stub.
    """
    _logger.info(
        "interaction stub: kind=%s target=%s payload=%s",
        proposal.kind,
        proposal.target_id,
        proposal.payload,
    )
    return InteractionState(status=STATUS_OPEN, ui_directive=UI_DIRECTIVE_STUB)


_STUB_DISPATCH: dict[str, Callable[[InteractionProposal], InteractionState]] = {
    "propose_quest":    _stub_handler,
    "claim_completion": _stub_handler,
}

_TRADE_KINDS = frozenset({"propose_trade", "give_item"})


def dispatch_interaction(proposal: InteractionProposal) -> InteractionState:
    """Route a proposal to its registered handler and return the result.

    propose_trade and give_item are delegated to the injected SyncTradeHandlerProtocol.
    propose_quest and claim_completion remain stubs in this slice.
    Unknown kinds fall through to a no-op state.

    Args:
        proposal: Interaction proposal extracted from a dialogue action field.

    Returns:
        InteractionState describing the outcome and which UI to show.
    """
    if proposal.kind in _TRADE_KINDS:
        return _trade_handler.handle(proposal)
    handler = _STUB_DISPATCH.get(proposal.kind)
    if handler is None:
        return InteractionState(status=STATUS_OPEN, ui_directive="none")
    return handler(proposal)
