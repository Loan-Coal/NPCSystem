"""
Module: trade_handler_sync
Layer: engines
Purpose: Defines SyncTradeHandlerProtocol (ISP-compliant, one method) and
         MinimalSyncTradeHandler — a deterministic, no-DB trade handler that
         validates proposal payload and returns STATUS_PENDING with echoed item
         details. Used as the default injection in dispatch.py.
Does NOT: call the database, issue HTTP requests, call LLMs, or mutate any state.
Dependencies injected: None. MinimalSyncTradeHandler is a pure data transformer.
Used by: engines.interaction.dispatch (as default _trade_handler value).
"""

from __future__ import annotations

from typing import Any, Protocol

from npc_engine.engines.interaction.models import (
    STATUS_PENDING,
    InteractionProposal,
    InteractionState,
)

_DEFAULT_QTY = 1


class SyncTradeHandlerProtocol(Protocol):
    """Protocol for synchronous trade proposal handlers.

    ISP note: one method only. Callers that need async trade handling should
    use the async handler in api/routes/interaction.py instead.
    """

    def handle(self, proposal: InteractionProposal) -> InteractionState:
        """Process a trade proposal and return the resulting interaction state.

        Args:
            proposal: The validated trade or give_item proposal to handle.

        Returns:
            InteractionState describing the outcome.

        Raises:
            ValueError: When the proposal payload is missing required fields.
        """
        ...


class MinimalSyncTradeHandler:
    """Deterministic, no-DB trade handler used as dispatch.py default.

    Validates that proposal.payload contains item_type, then returns an
    InteractionState with status=STATUS_PENDING and echoed item details.
    No randomness, no I/O, no LLM calls.
    """

    def handle(self, proposal: InteractionProposal) -> InteractionState:
        """Validate and process a propose_trade or give_item proposal.

        Args:
            proposal: Interaction proposal with kind propose_trade or give_item.

        Returns:
            InteractionState(status=STATUS_PENDING, ui_directive="show_trade",
            metadata={"item_type": ..., "qty": ...}).

        Raises:
            ValueError: When payload is missing the required item_type field.
        """
        payload: dict[str, Any] = proposal.payload
        item_type = payload.get("item_type")
        if not item_type:
            raise ValueError(
                f"Trade proposal payload missing required field 'item_type'. "
                f"Received payload: {payload!r}"
            )
        qty: int = int(payload.get("qty", _DEFAULT_QTY))
        return InteractionState(
            status=STATUS_PENDING,
            ui_directive="show_trade",
            metadata={"item_type": item_type, "qty": qty},
        )
