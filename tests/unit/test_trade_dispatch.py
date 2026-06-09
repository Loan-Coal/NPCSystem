"""
Module: test_trade_dispatch
Layer: tests/unit
Purpose: Unit tests for EXP-40 SyncTradeHandlerProtocol + MinimalSyncTradeHandler,
         NegotiationBackedSyncTradeHandler, and dispatch_interaction routing for
         propose_trade/give_item.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from npc_engine.engines.interaction.models import (
    InteractionProposal,
    InteractionState,
    STATUS_OPEN,
    STATUS_PENDING,
)
from npc_engine.engines.interaction.trade_handler_sync import (
    MinimalSyncTradeHandler,
    NegotiationBackedSyncTradeHandler,
    SyncTradeHandlerProtocol,
)
from npc_engine.engines.interaction.dispatch import (
    dispatch_interaction,
    set_trade_handler,
)
from npc_engine.engines.interaction.negotiation_store import NegotiationStore
from npc_engine.engines.economy.pricing_engine import PricingEngine


# ---------------------------------------------------------------------------
# MinimalSyncTradeHandler — happy path
# ---------------------------------------------------------------------------


def test_minimal_handler_returns_pending_with_item_echo() -> None:
    """propose_trade with valid payload returns STATUS_PENDING and echoes item details."""
    handler = MinimalSyncTradeHandler()
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="aldric_merchant",
        payload={"item_type": "iron_sword", "qty": 2},
    )
    result: InteractionState = handler.handle(proposal, player_id="p1", npc_id="npc1")
    assert result.status == STATUS_PENDING
    assert result.ui_directive == "show_trade"
    assert result.metadata is not None
    assert result.metadata["item_type"] == "iron_sword"
    assert result.metadata["qty"] == 2


def test_minimal_handler_defaults_qty_to_one() -> None:
    """propose_trade without qty defaults qty to 1 in returned metadata."""
    handler = MinimalSyncTradeHandler()
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="aldric_merchant",
        payload={"item_type": "potion"},
    )
    result = handler.handle(proposal, player_id="p1", npc_id="npc1")
    assert result.status == STATUS_PENDING
    assert result.metadata is not None
    assert result.metadata["qty"] == 1


# ---------------------------------------------------------------------------
# MinimalSyncTradeHandler — validation failure
# ---------------------------------------------------------------------------


def test_minimal_handler_raises_on_missing_item_type() -> None:
    """Missing item_type in payload raises ValueError — not silent stub pass-through."""
    handler = MinimalSyncTradeHandler()
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="aldric_merchant",
        payload={"qty": 3},
    )
    with pytest.raises(ValueError, match="item_type"):
        handler.handle(proposal, player_id="p1", npc_id="npc1")


# ---------------------------------------------------------------------------
# dispatch_interaction routing
# ---------------------------------------------------------------------------


def test_dispatch_propose_trade_returns_pending() -> None:
    """dispatch_interaction routes propose_trade to the real handler (STATUS_PENDING)."""
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="aldric_merchant",
        payload={"item_type": "grain", "qty": 5},
    )
    result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
    assert result.status == STATUS_PENDING


def test_dispatch_give_item_returns_pending() -> None:
    """dispatch_interaction routes give_item to the real handler (STATUS_PENDING)."""
    proposal = InteractionProposal(
        kind="give_item",
        target_id="mira_innkeeper",
        payload={"item_type": "bread", "qty": 1},
    )
    result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
    assert result.status == STATUS_PENDING


def test_dispatch_propose_quest_still_uses_stub() -> None:
    """propose_quest is NOT upgraded in this slice — stub returns STATUS_OPEN."""
    proposal = InteractionProposal(
        kind="propose_quest",
        target_id="captain_sorn",
        payload={},
    )
    result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
    assert result.status == STATUS_OPEN


# ---------------------------------------------------------------------------
# Injection seam: set_trade_handler
# ---------------------------------------------------------------------------


def test_injected_handler_is_called() -> None:
    """An injected mock handler is called instead of MinimalSyncTradeHandler."""
    mock_handler = MagicMock(spec=SyncTradeHandlerProtocol)
    mock_handler.handle.return_value = InteractionState(
        status=STATUS_PENDING,
        ui_directive="show_trade",
    )

    set_trade_handler(mock_handler)
    try:
        proposal = InteractionProposal(
            kind="propose_trade",
            target_id="aldric_merchant",
            payload={"item_type": "silk", "qty": 10},
        )
        result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
        mock_handler.handle.assert_called_once_with(proposal, "p1", "npc1")
        assert result.status == STATUS_PENDING
    finally:
        # Restore default handler so other tests are unaffected
        set_trade_handler(MinimalSyncTradeHandler())


# ---------------------------------------------------------------------------
# NegotiationBackedSyncTradeHandler — happy path (opens session)
# ---------------------------------------------------------------------------


def test_negotiation_backed_handler_returns_status_open() -> None:
    """handle() with valid item_type opens a session and returns STATUS_OPEN."""
    mock_pricing = MagicMock(spec=PricingEngine)
    mock_pricing.compute_price.return_value = 100
    store = NegotiationStore()

    handler = NegotiationBackedSyncTradeHandler(store=store, pricing_engine=mock_pricing)
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="item_sword",
        payload={"item_type": "iron_sword"},
    )
    result = handler.handle(proposal, player_id="p1", npc_id="npc1")

    assert result.status == STATUS_OPEN
    mock_pricing.compute_price.assert_called_once_with(
        item_type="iron_sword",
        location_type="",
        active_event_types=[],
        is_faction_member=False,
    )


# ---------------------------------------------------------------------------
# NegotiationBackedSyncTradeHandler — validation failure
# ---------------------------------------------------------------------------


def test_negotiation_backed_handler_raises_on_missing_item_type() -> None:
    """Missing item_type payload raises ValueError."""
    mock_pricing = MagicMock(spec=PricingEngine)
    store = NegotiationStore()

    handler = NegotiationBackedSyncTradeHandler(store=store, pricing_engine=mock_pricing)
    proposal = InteractionProposal(
        kind="propose_trade",
        target_id="item_sword",
        payload={"qty": 2},
    )
    with pytest.raises(ValueError, match="item_type required"):
        handler.handle(proposal, player_id="p1", npc_id="npc1")
