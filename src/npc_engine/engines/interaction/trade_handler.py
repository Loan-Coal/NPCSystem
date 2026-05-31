"""
Module: trade_handler
Layer: engines
Purpose: Processes trade interaction proposals — opens NegotiationSessions and
         evaluates move grammar (currency_offer, defer_payment, invalid moves).
Does NOT: write to the graph, call LLM, or perform HTTP.
         Graph debt-edge write for defer_payment is delegated to the route layer.
Dependencies injected: NegotiationStore, center_price (caller computes via PricingEngine).
Used by: api.routes.interaction
"""

from __future__ import annotations

import logging

from npc_engine.engines.interaction.models import (
    InteractionProposal,
    InteractionState,
    STATUS_OPEN,
    STATUS_PENDING_CONFIRM,
    STATUS_ACCEPTED,
    UI_DIRECTIVE_TRADE,
    UI_DIRECTIVE_NONE,
)
from npc_engine.engines.interaction.negotiation_store import (
    MoveRecord,
    NegotiationSession,
    NegotiationStore,
)

_logger = logging.getLogger(__name__)

_VALID_MOVES = frozenset({"currency_offer", "defer_payment"})
_INVALID_MOVE_HINT = "npc_refuses_invalid_offer"
_LOW_OFFER_HINT = "npc_counters_low_offer"


def open_or_resume_trade(
    proposal: InteractionProposal,
    player_id: str,
    seller_id: str,
    center_price: int,
    store: NegotiationStore,
) -> InteractionState:
    """Open a new NegotiationSession or resume an existing one for propose_trade.

    If a session is already open for this player and the same item, resume it.
    If the proposal has no move in the payload, just open/return the current state.
    If the payload contains a move, process it.

    Args:
        proposal: InteractionProposal with kind="propose_trade".
        player_id: Player character ID.
        seller_id: NPC character ID acting as seller.
        center_price: Deterministic fair price from the pricing engine.
        store: Active NegotiationStore (single instance per app).

    Returns:
        InteractionState describing the current trade session state.
    """
    item_id = proposal.target_id or ""
    item_type = proposal.payload.get("item_type", "unknown")
    move = proposal.payload.get("move")

    existing = store.get(player_id)
    if existing is None or existing.item_id != item_id or existing.status in (STATUS_ACCEPTED, "declined"):
        session = NegotiationSession(
            item_id=item_id,
            item_type=item_type,
            seller_id=seller_id,
            center_price=center_price,
            threshold=center_price,
            current_offer=None,
            moves=(),
            status=STATUS_OPEN,
            accumulated_band=0.0,
        )
        store.put(player_id, session)
        _logger.info("trade session opened: player=%s item=%s center=%d", player_id, item_id, center_price)
    else:
        session = existing

    if move is None:
        return InteractionState(
            status=session.status,
            ui_directive=UI_DIRECTIVE_TRADE,
            data=session.to_dict(),
        )

    return _process_move(session, player_id, move, proposal.payload, store)


def handle_offer_at_asking_price(
    player_id: str,
    store: NegotiationStore,
) -> InteractionState:
    """Process a currency offer at the current asking-price (threshold).

    Used by the demo's 'OFFER ASKING PRICE' shortcut. Delegates to
    _handle_currency_offer with amount=session.threshold so the session
    transitions to pending_confirm when the offer equals the ask.

    Args:
        player_id: Player character ID.
        store: Active NegotiationStore.

    Returns:
        InteractionState — pending_confirm if session is open, open otherwise.
    """
    session = store.get(player_id)
    if session is None or session.status != STATUS_OPEN:
        return InteractionState(
            status=STATUS_OPEN,
            ui_directive=UI_DIRECTIVE_NONE,
            narration_hint=None,
            data=session.to_dict() if session else None,
        )
    return _handle_currency_offer(session, player_id, {"amount": session.threshold}, store)


def apply_band_update(
    player_id: str,
    trust: int,
    affection: int,
    store: NegotiationStore,
) -> None:
    """Shift the disposition band for an open session after a dialogue turn.

    Args:
        player_id: Player character ID.
        trust: Trust relation delta from this turn.
        affection: Affection relation delta from this turn.
        store: Active NegotiationStore.
    """
    session = store.get(player_id)
    if session is None or session.status != STATUS_OPEN:
        return
    updated = session.apply_band_delta(trust, affection)
    store.put(player_id, updated)


def _process_move(
    session: NegotiationSession,
    player_id: str,
    move: str,
    payload: dict,
    store: NegotiationStore,
) -> InteractionState:
    """Dispatch a named move to its handler and persist the result.

    Args:
        session: Current session state.
        player_id: Player character ID.
        move: Move kind string.
        payload: Full proposal payload dict.
        store: Active NegotiationStore.

    Returns:
        InteractionState after processing the move.
    """
    if move not in _VALID_MOVES:
        _logger.info("trade invalid move: player=%s move=%s", player_id, move)
        return InteractionState(
            status=STATUS_OPEN,
            ui_directive=UI_DIRECTIVE_TRADE,
            narration_hint=_INVALID_MOVE_HINT,
            data=session.to_dict(),
        )

    if move == "currency_offer":
        return _handle_currency_offer(session, player_id, payload, store)

    # defer_payment — route layer creates the HAS_DEBT edge; we return accepted.
    record = MoveRecord(kind="defer_payment", value=session.center_price, accepted=True)
    updated = session.with_move(record, new_status=STATUS_ACCEPTED)
    store.put(player_id, updated)
    _logger.info("trade deferred: player=%s item=%s amount=%d", player_id, session.item_id, session.center_price)
    return InteractionState(
        status=STATUS_ACCEPTED,
        ui_directive=UI_DIRECTIVE_TRADE,
        narration_hint="npc_deferred_payment_accepted",
        data=updated.to_dict(),
    )


def _handle_currency_offer(
    session: NegotiationSession,
    player_id: str,
    payload: dict,
    store: NegotiationStore,
) -> InteractionState:
    """Handle a currency_offer move: accept if amount >= threshold else refuse.

    Args:
        session: Current session state.
        player_id: Player character ID.
        payload: Proposal payload; must contain ``amount`` (int).
        store: Active NegotiationStore.

    Returns:
        InteractionState — pending_confirm if accepted, open if refused.
    """
    try:
        amount = int(payload["amount"])
    except (KeyError, TypeError, ValueError):
        return InteractionState(
            status=STATUS_OPEN,
            ui_directive=UI_DIRECTIVE_TRADE,
            narration_hint="npc_asks_for_specific_amount",
            data=session.to_dict(),
        )

    accepted = amount >= session.threshold
    record = MoveRecord(kind="currency_offer", value=amount, accepted=accepted)

    if accepted:
        updated = session.with_move(record, new_offer=amount, new_status=STATUS_PENDING_CONFIRM)
        store.put(player_id, updated)
        _logger.info("trade offer accepted: player=%s amount=%d threshold=%d", player_id, amount, session.threshold)
        return InteractionState(
            status=STATUS_PENDING_CONFIRM,
            ui_directive=UI_DIRECTIVE_TRADE,
            narration_hint="npc_accepts_offer",
            data=updated.to_dict(),
        )

    updated = session.with_move(record, new_offer=amount)
    store.put(player_id, updated)
    _logger.info("trade offer refused: player=%s amount=%d threshold=%d", player_id, amount, session.threshold)
    return InteractionState(
        status=STATUS_OPEN,
        ui_directive=UI_DIRECTIVE_TRADE,
        narration_hint=_LOW_OFFER_HINT,
        data=updated.to_dict(),
    )
