"""
Module: trade_models
Layer: engines
Purpose: Frozen dataclass DTOs for trade offer/result payloads.
Does NOT: perform I/O or business logic.
Dependencies: none
Dependencies injected: None.
Used by: npc_engine.engines.economy.trade_engine, npc_engine.api.routes.economy
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeResult:
    """Immutable result of a trade offer evaluation.

    Attributes:
        accepted: True if the offer was accepted and the transfer executed.
        fair_price: The engine-computed fair price for the item.
        final_price: The agreed price paid; None when the offer was rejected.
        rejection_reason: Human-readable explanation when offer is rejected; None on accept.
    """

    accepted: bool
    fair_price: int
    final_price: int | None
    rejection_reason: str | None
