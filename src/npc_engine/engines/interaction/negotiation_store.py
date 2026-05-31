"""
Module: negotiation_store
Layer: engines
Purpose: In-memory per-player NegotiationSession store for the trade barter loop.
         Holds the live session between the LLM proposal and the player's confirm click.
Does NOT: persist to graph, perform price lookups, or call HTTP.
Dependencies injected: None (plain Python, no I/O).
Used by: engines.interaction.trade_handler, api.routes.interaction
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


_BAND_MIN: float = -0.10
_BAND_MAX: float = +0.15


@dataclass(frozen=True)
class MoveRecord:
    """One move made during a negotiation session.

    Attributes:
        kind: Move type — ``"currency_offer"``, ``"defer_payment"``, or
            ``"invalid"`` for moves refused in-character.
        value: The move's principal value (e.g. offered amount).
        accepted: True when this move advanced the session to pending_confirm
            or accepted.
    """

    kind: str
    value: Any
    accepted: bool


@dataclass(frozen=True)
class NegotiationSession:
    """Live trade negotiation state for one (player, NPC) pair.

    Attributes:
        item_id: Graph ID of the item being negotiated.
        item_type: Item category string used by the pricing engine.
        seller_id: NPC character ID.
        center_price: Deterministic fair price from the pricing engine.
        threshold: Current acceptance floor — ``center_price × (1 − band)``.
        current_offer: Most recent currency offer from the player (or None).
        moves: Ordered list of moves made this session.
        status: Lifecycle — ``"open"``, ``"pending_confirm"``, ``"accepted"``,
            ``"declined"``.
        accumulated_band: Running disposition band in ``[−0.10, +0.15]``.
    """

    item_id: str
    item_type: str
    seller_id: str
    center_price: int
    threshold: int
    current_offer: int | None
    moves: tuple[MoveRecord, ...]
    status: str
    accumulated_band: float

    def apply_band_delta(self, trust: int, affection: int) -> NegotiationSession:
        """Return a new session with the disposition band shifted by one turn's deltas.

        Args:
            trust: Trust delta from this dialogue turn (−100 … +100).
            affection: Affection delta from this dialogue turn.

        Returns:
            Updated NegotiationSession with recalculated threshold.
        """
        delta = trust * 0.005 + affection * 0.003
        new_band = max(_BAND_MIN, min(_BAND_MAX, self.accumulated_band + delta))
        new_threshold = max(1, math.floor(self.center_price * (1.0 - new_band)))
        return NegotiationSession(
            item_id=self.item_id,
            item_type=self.item_type,
            seller_id=self.seller_id,
            center_price=self.center_price,
            threshold=new_threshold,
            current_offer=self.current_offer,
            moves=self.moves,
            status=self.status,
            accumulated_band=new_band,
        )

    def with_move(self, move: MoveRecord, *, new_offer: int | None = None, new_status: str | None = None) -> NegotiationSession:
        """Return a new session with a move appended and optional field overrides.

        Args:
            move: The move to append.
            new_offer: Override current_offer when provided.
            new_status: Override status when provided.

        Returns:
            Updated NegotiationSession.
        """
        return NegotiationSession(
            item_id=self.item_id,
            item_type=self.item_type,
            seller_id=self.seller_id,
            center_price=self.center_price,
            threshold=self.threshold,
            current_offer=new_offer if new_offer is not None else self.current_offer,
            moves=self.moves + (move,),
            status=new_status if new_status is not None else self.status,
            accumulated_band=self.accumulated_band,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot dict for the demo client."""
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "seller_id": self.seller_id,
            "center_price": self.center_price,
            "threshold": self.threshold,
            "current_offer": self.current_offer,
            "moves": [{"kind": m.kind, "value": m.value, "accepted": m.accepted} for m in self.moves],
            "status": self.status,
            "accumulated_band": round(self.accumulated_band, 4),
        }


class NegotiationStore:
    """In-memory store for one active NegotiationSession per player.

    Single-player demo assumption: keyed by player_id. Thread-safe for
    single-threaded FastAPI event loop — do not use from multiple threads.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, NegotiationSession] = {}

    def get(self, player_id: str) -> NegotiationSession | None:
        """Return the active session for player_id, or None."""
        return self._sessions.get(player_id)

    def put(self, player_id: str, session: NegotiationSession) -> None:
        """Store or replace the session for player_id."""
        self._sessions[player_id] = session

    def clear(self, player_id: str) -> None:
        """Remove the session for player_id (no-op if absent)."""
        self._sessions.pop(player_id, None)
