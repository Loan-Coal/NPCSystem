"""
Module: test_trade_dispatch
Layer: tests/unit
Purpose: Unit tests for EXP-40 SyncTradeHandlerProtocol + MinimalSyncTradeHandler,
         NegotiationBackedSyncTradeHandler, dispatch_interaction routing for
         propose_trade/give_item, and EXP-216 composition-root wiring.
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


def test_dispatch_propose_trade_routes_to_minimal_handler() -> None:
    """dispatch_interaction routes propose_trade to MinimalSyncTradeHandler (STATUS_PENDING).

    Explicitly wires MinimalSyncTradeHandler so this test is independent of the
    EXP-216 composition-root default.
    """
    set_trade_handler(MinimalSyncTradeHandler())
    try:
        proposal = InteractionProposal(
            kind="propose_trade",
            target_id="aldric_merchant",
            payload={"item_type": "grain", "qty": 5},
        )
        result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
        assert result.status == STATUS_PENDING
    finally:
        set_trade_handler(MinimalSyncTradeHandler())


def test_dispatch_give_item_routes_to_minimal_handler() -> None:
    """dispatch_interaction routes give_item to MinimalSyncTradeHandler (STATUS_PENDING).

    Explicitly wires MinimalSyncTradeHandler so this test is independent of the
    EXP-216 composition-root default.
    """
    set_trade_handler(MinimalSyncTradeHandler())
    try:
        proposal = InteractionProposal(
            kind="give_item",
            target_id="mira_innkeeper",
            payload={"item_type": "bread", "qty": 1},
        )
        result = dispatch_interaction(proposal, player_id="p1", npc_id="npc1")
        assert result.status == STATUS_PENDING
    finally:
        set_trade_handler(MinimalSyncTradeHandler())


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


# ---------------------------------------------------------------------------
# EXP-216: composition-root wiring — dispatch uses NegotiationBackedSyncTradeHandler
# ---------------------------------------------------------------------------


def test_composition_root_wires_negotiation_backed_handler() -> None:
    """EXP-216: get_sync_trade_handler() returns NegotiationBackedSyncTradeHandler.

    After calling set_trade_handler with the composition-root factory result,
    dispatch_interaction for propose_trade opens a NegotiationSession and
    returns STATUS_OPEN — not STATUS_PENDING (MinimalSyncTradeHandler behaviour).
    """
    from npc_engine.api.dependencies import get_sync_trade_handler

    handler = get_sync_trade_handler()
    assert isinstance(handler, NegotiationBackedSyncTradeHandler), (
        f"Expected NegotiationBackedSyncTradeHandler from composition root, "
        f"got {type(handler).__name__}"
    )

    set_trade_handler(handler)
    try:
        proposal = InteractionProposal(
            kind="propose_trade",
            target_id="aldric_merchant",
            payload={"item_type": "iron_sword", "qty": 1},
        )
        result = dispatch_interaction(proposal, player_id="p1", npc_id="aldric_merchant")
        assert result.status == STATUS_OPEN, (
            f"Expected STATUS_OPEN from NegotiationBackedSyncTradeHandler, "
            f"got {result.status!r} — dispatch default is not yet wired"
        )
    finally:
        set_trade_handler(MinimalSyncTradeHandler())


def test_dispatch_default_is_negotiation_backed() -> None:
    """EXP-216: get_sync_trade_handler() wires NegotiationBackedSyncTradeHandler into dispatch.

    Calls the composition root factory and then asserts dispatch._trade_handler
    is NegotiationBackedSyncTradeHandler — verifying the factory performs the
    wiring side-effect required by EXP-216.

    RED reason when failing: get_sync_trade_handler() does not call set_trade_handler,
    so dispatch._trade_handler stays as MinimalSyncTradeHandler after the call.
    """
    import npc_engine.engines.interaction.dispatch as dispatch_mod
    from npc_engine.api.dependencies import get_sync_trade_handler

    # Reset to Minimal so the test is independent of execution order.
    set_trade_handler(MinimalSyncTradeHandler())
    assert isinstance(dispatch_mod._trade_handler, MinimalSyncTradeHandler), (
        "Pre-condition: reset to MinimalSyncTradeHandler failed"
    )

    # Act: call the composition root — it must wire the dispatch as a side-effect.
    get_sync_trade_handler.cache_clear()
    try:
        get_sync_trade_handler()

        # Assert: dispatch is now wired to the Negotiation-backed handler.
        assert isinstance(dispatch_mod._trade_handler, NegotiationBackedSyncTradeHandler), (
            f"dispatch._trade_handler is {type(dispatch_mod._trade_handler).__name__!r} after "
            f"get_sync_trade_handler(); expected NegotiationBackedSyncTradeHandler. "
            f"EXP-216: get_sync_trade_handler() must call set_trade_handler(handler)."
        )
    finally:
        # Restore Minimal so subsequent tests that rely on STATUS_PENDING are unaffected.
        get_sync_trade_handler.cache_clear()
        set_trade_handler(MinimalSyncTradeHandler())
