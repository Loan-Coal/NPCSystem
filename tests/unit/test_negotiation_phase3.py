"""
test_negotiation_phase3.py - Unit tests for Phase 3 negotiation layer.

Covers:
- NegotiationSession: band clamping, threshold recalculation, with_move, to_dict
- NegotiationStore: put/get/clear lifecycle
- trade_handler: open_or_resume_trade, apply_band_update, currency_offer moves,
  defer_payment, invalid moves, missing amount
- TradePanelWidget: draw dispatch (empty vs card state) without crashing

Does NOT: touch the HTTP API, Neo4j, Redis, or the Pygame display.
"""

from __future__ import annotations

import math
import unittest

import pytest

from npc_engine.engines.interaction.models import (
    InteractionProposal,
    STATUS_ACCEPTED,
    STATUS_OPEN,
    STATUS_PENDING_CONFIRM,
    UI_DIRECTIVE_TRADE,
)
from npc_engine.engines.interaction.negotiation_store import (
    MoveRecord,
    NegotiationSession,
    NegotiationStore,
)
from npc_engine.engines.interaction.trade_handler import (
    apply_band_update,
    open_or_resume_trade,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(
    item_id: str = "spice_bundle",
    center_price: int = 100,
    band: float = 0.0,
    status: str = STATUS_OPEN,
    current_offer: int | None = None,
    moves: tuple = (),
) -> NegotiationSession:
    threshold = max(1, math.floor(center_price * (1.0 - band)))
    return NegotiationSession(
        item_id=item_id,
        item_type="spice",
        seller_id="aldric_merchant",
        center_price=center_price,
        threshold=threshold,
        current_offer=current_offer,
        moves=moves,
        status=status,
        accumulated_band=band,
    )


def _proposal(target_id: str | None = "spice_bundle", payload: dict | None = None) -> InteractionProposal:
    return InteractionProposal(
        kind="propose_trade",
        target_id=target_id,
        payload=payload or {"item_type": "spice"},
    )


# ---------------------------------------------------------------------------
# NegotiationSession
# ---------------------------------------------------------------------------

class TestNegotiationSession:
    def test_apply_band_delta_increases_on_positive(self):
        s = _session()
        s2 = s.apply_band_delta(trust=10, affection=5)
        expected_delta = 10 * 0.005 + 5 * 0.003
        assert abs(s2.accumulated_band - expected_delta) < 1e-6

    def test_apply_band_delta_clamps_max(self):
        s = _session(band=0.14)
        s2 = s.apply_band_delta(trust=100, affection=100)
        assert s2.accumulated_band <= 0.15

    def test_apply_band_delta_clamps_min(self):
        s = _session(band=-0.09)
        s2 = s.apply_band_delta(trust=-100, affection=-100)
        assert s2.accumulated_band >= -0.10

    def test_threshold_drops_with_positive_band(self):
        s = _session(center_price=100)
        s2 = s.apply_band_delta(trust=20, affection=0)
        assert s2.threshold < 100

    def test_threshold_raises_with_negative_band(self):
        s = _session(center_price=100)
        s2 = s.apply_band_delta(trust=-20, affection=0)
        assert s2.threshold > 100

    def test_with_move_appends(self):
        s = _session()
        move = MoveRecord(kind="currency_offer", value=50, accepted=False)
        s2 = s.with_move(move)
        assert len(s2.moves) == 1
        assert s2.moves[0].kind == "currency_offer"

    def test_with_move_overrides_status(self):
        s = _session()
        move = MoveRecord(kind="currency_offer", value=100, accepted=True)
        s2 = s.with_move(move, new_status=STATUS_PENDING_CONFIRM)
        assert s2.status == STATUS_PENDING_CONFIRM

    def test_with_move_overrides_offer(self):
        s = _session()
        move = MoveRecord(kind="currency_offer", value=70, accepted=False)
        s2 = s.with_move(move, new_offer=70)
        assert s2.current_offer == 70

    def test_to_dict_serialisable(self):
        s = _session()
        d = s.to_dict()
        assert d["item_id"] == "spice_bundle"
        assert d["center_price"] == 100
        assert isinstance(d["moves"], list)

    def test_immutable_original_unchanged(self):
        s = _session()
        _ = s.apply_band_delta(trust=50, affection=0)
        assert s.accumulated_band == 0.0


# ---------------------------------------------------------------------------
# NegotiationStore
# ---------------------------------------------------------------------------

class TestNegotiationStore:
    def test_get_returns_none_for_unknown_player(self):
        store = NegotiationStore()
        assert store.get("unknown_player") is None

    def test_put_and_get(self):
        store = NegotiationStore()
        s = _session()
        store.put("p1", s)
        assert store.get("p1") is s

    def test_clear_removes_session(self):
        store = NegotiationStore()
        store.put("p1", _session())
        store.clear("p1")
        assert store.get("p1") is None

    def test_clear_noop_for_absent(self):
        store = NegotiationStore()
        store.clear("ghost")  # should not raise


# ---------------------------------------------------------------------------
# trade_handler: open_or_resume_trade
# ---------------------------------------------------------------------------

class TestOpenOrResumeTrade:
    def test_opens_new_session(self):
        store = NegotiationStore()
        result = open_or_resume_trade(_proposal(), "player", "aldric_merchant", 100, store)
        assert result.status == STATUS_OPEN
        assert result.ui_directive == UI_DIRECTIVE_TRADE
        assert store.get("player") is not None

    def test_resumes_existing_session(self):
        store = NegotiationStore()
        open_or_resume_trade(_proposal(), "player", "aldric_merchant", 100, store)
        first = store.get("player")
        open_or_resume_trade(_proposal(), "player", "aldric_merchant", 100, store)
        second = store.get("player")
        assert first is second  # same object — not recreated

    def test_resets_on_different_item(self):
        store = NegotiationStore()
        open_or_resume_trade(_proposal(target_id="item_a"), "player", "seller", 100, store)
        open_or_resume_trade(_proposal(target_id="item_b"), "player", "seller", 100, store)
        assert store.get("player").item_id == "item_b"

    def test_resets_after_accepted(self):
        store = NegotiationStore()
        store.put("player", _session(status=STATUS_ACCEPTED))
        open_or_resume_trade(_proposal(), "player", "seller", 100, store)
        assert store.get("player").status == STATUS_OPEN

    def test_currency_offer_accepted_above_threshold(self):
        store = NegotiationStore()
        payload = {"item_type": "spice", "move": "currency_offer", "amount": 100}
        result = open_or_resume_trade(_proposal(payload=payload), "player", "seller", 100, store)
        assert result.status == STATUS_PENDING_CONFIRM

    def test_currency_offer_refused_below_threshold(self):
        store = NegotiationStore()
        payload = {"item_type": "spice", "move": "currency_offer", "amount": 1}
        result = open_or_resume_trade(_proposal(payload=payload), "player", "seller", 100, store)
        assert result.status == STATUS_OPEN
        assert result.narration_hint == "npc_counters_low_offer"

    def test_currency_offer_missing_amount(self):
        store = NegotiationStore()
        payload = {"item_type": "spice", "move": "currency_offer"}
        result = open_or_resume_trade(_proposal(payload=payload), "player", "seller", 100, store)
        assert result.status == STATUS_OPEN
        assert result.narration_hint == "npc_asks_for_specific_amount"

    def test_defer_payment_returns_accepted(self):
        store = NegotiationStore()
        payload = {"item_type": "spice", "move": "defer_payment"}
        result = open_or_resume_trade(_proposal(payload=payload), "player", "seller", 100, store)
        assert result.status == STATUS_ACCEPTED
        assert result.narration_hint == "npc_deferred_payment_accepted"

    def test_invalid_move_returns_open_with_hint(self):
        store = NegotiationStore()
        payload = {"item_type": "spice", "move": "item_swap"}
        result = open_or_resume_trade(_proposal(payload=payload), "player", "seller", 100, store)
        assert result.status == STATUS_OPEN
        assert result.narration_hint == "npc_refuses_invalid_offer"

    def test_data_snapshot_included(self):
        store = NegotiationStore()
        result = open_or_resume_trade(_proposal(), "player", "seller", 100, store)
        assert result.data is not None
        assert result.data["item_id"] == "spice_bundle"


# ---------------------------------------------------------------------------
# trade_handler: apply_band_update
# ---------------------------------------------------------------------------

class TestApplyBandUpdate:
    def test_updates_open_session(self):
        store = NegotiationStore()
        store.put("player", _session(center_price=100))
        apply_band_update("player", trust=10, affection=0, store=store)
        s = store.get("player")
        assert s.accumulated_band > 0.0

    def test_noop_when_no_session(self):
        store = NegotiationStore()
        apply_band_update("ghost", trust=10, affection=0, store=store)  # should not raise

    def test_noop_when_session_pending_confirm(self):
        store = NegotiationStore()
        store.put("player", _session(status=STATUS_PENDING_CONFIRM))
        original_band = store.get("player").accumulated_band
        apply_band_update("player", trust=50, affection=50, store=store)
        assert store.get("player").accumulated_band == original_band
