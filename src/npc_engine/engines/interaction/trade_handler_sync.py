"""
Module: trade_handler_sync
Layer: engines
Purpose: Defines SyncTradeHandlerProtocol (ISP-compliant, one method),
         MinimalSyncTradeHandler — a deterministic, no-DB echo handler, and
         NegotiationBackedSyncTradeHandler — a real handler that wraps
         open_or_resume_trade with PricingEngine-computed center prices.
Does NOT: call the database directly, issue HTTP requests, or call LLMs.
Dependencies injected: NegotiationStore and PricingEngine (for NegotiationBackedSyncTradeHandler).
Used by: engines.interaction.dispatch (as injected _trade_handler value).
"""

from __future__ import annotations

from typing import Any, Protocol

from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.interaction.models import (
    STATUS_PENDING,
    InteractionProposal,
    InteractionState,
)
from npc_engine.engines.interaction.negotiation_store import NegotiationStore
from npc_engine.engines.interaction.trade_handler import open_or_resume_trade

_DEFAULT_QTY = 1
_DEFAULT_LOCATION_TYPE = ""
_DEFAULT_ACTIVE_EVENTS: list[str] = []
_DEFAULT_IS_FACTION_MEMBER = False


class SyncTradeHandlerProtocol(Protocol):
    """Protocol for synchronous trade proposal handlers.

    ISP note: one method only. Callers that need async trade handling should
    use the async handler in api/routes/interaction.py instead.
    """

    def handle(
        self,
        proposal: InteractionProposal,
        player_id: str = "",
        npc_id: str = "",
    ) -> InteractionState:
        """Process a trade proposal and return the resulting interaction state.

        Args:
            proposal: The validated trade or give_item proposal to handle.
            player_id: Player character ID (used by session-backed handlers).
            npc_id: NPC character ID acting as seller (used by session-backed handlers).

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

    def handle(
        self,
        proposal: InteractionProposal,
        player_id: str = "",
        npc_id: str = "",
    ) -> InteractionState:
        """Validate and process a propose_trade or give_item proposal.

        Args:
            proposal: Interaction proposal with kind propose_trade or give_item.
            player_id: Ignored by this handler (kept for protocol compatibility).
            npc_id: Ignored by this handler (kept for protocol compatibility).

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


class NegotiationBackedSyncTradeHandler:
    """Synchronous trade handler that opens/resumes a real NegotiationSession.

    Wraps open_or_resume_trade with a PricingEngine-computed center price.
    No async. No LLM calls. No graph writes.
    """

    def __init__(self, store: NegotiationStore, pricing_engine: PricingEngine) -> None:
        """Initialise with a shared NegotiationStore and a PricingEngine.

        Args:
            store: Singleton NegotiationStore for the lifetime of the app.
            pricing_engine: Pricing engine used to compute center prices.
        """
        self._store = store
        self._pricing_engine = pricing_engine

    def handle(
        self,
        proposal: InteractionProposal,
        player_id: str = "",
        npc_id: str = "",
    ) -> InteractionState:
        """Open or resume a NegotiationSession for the given trade proposal.

        Args:
            proposal: Interaction proposal with kind propose_trade; payload must
                contain item_type.
            player_id: Player character ID used to key the NegotiationStore.
            npc_id: NPC character ID acting as seller.

        Returns:
            InteractionState with status=STATUS_OPEN and trade session data when
            no move is included in the payload.

        Raises:
            ValueError: When proposal.payload is missing the required item_type field.
        """
        item_type = proposal.payload.get("item_type")
        if item_type is None:
            raise ValueError("item_type required")
        center_price: int = self._pricing_engine.compute_price(
            item_type=item_type,
            location_type=_DEFAULT_LOCATION_TYPE,
            active_event_types=_DEFAULT_ACTIVE_EVENTS,
            is_faction_member=_DEFAULT_IS_FACTION_MEMBER,
        )
        return open_or_resume_trade(proposal, player_id, npc_id, center_price, self._store)
