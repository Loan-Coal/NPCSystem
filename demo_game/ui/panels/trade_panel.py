"""
Module: trade_panel
Layer: demo_game.ui
Purpose: Renders the TRADE tab — live negotiation state, offer/confirm buttons,
         and deferred-payment status. Non-modal; updated from negotiation_state dict.
Does NOT: make HTTP calls or hold business logic.
Dependencies injected: None (pure rendering + callback registration).
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE
from demo_game.ui.widgets.widgets import _wrap_text

_CLR_BG    = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY  = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED   = PALETTE["red"]
_CLR_PANEL = PALETTE["panel"]
_CLR_BORDER = PALETTE["border"]

_BTN_H = 30
_PAD   = 12


class TradePanelWidget:
    """Renders a live trade negotiation card in the TRADE right panel tab.

    Shows item, asking price (threshold), current offer, move history,
    and action buttons appropriate to the current session status.

    Buttons:
    - [OFFER ASKING PRICE] — visible when status=``"open"`` and session active
    - [CONFIRM TRADE]      — visible when status=``"pending_confirm"``
    - deferred text        — when status=``"accepted"`` via defer_payment

    Args:
        font_body: 14px font for item name and move history.
        font_label: 12px font for badges and button labels.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._state: dict | None = None
        self._npc_gold: int | None = None
        self._on_offer: Callable[[], None] | None = None
        self._on_confirm: Callable[[], None] | None = None
        self._btn_offer_rect: pygame.Rect | None = None
        self._btn_confirm_rect: pygame.Rect | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_negotiation_state(self, state: dict | None) -> None:
        """Replace the displayed negotiation state. Pass None to show empty state."""
        self._state = state

    def set_npc_gold(self, gold: int | None) -> None:
        """Set the NPC seller's currency balance to display in the trade card."""
        self._npc_gold = gold

    def get_state(self) -> dict | None:
        """Return the current negotiation state dict, or None."""
        return self._state

    def set_offer_callback(self, cb: Callable[[], None]) -> None:
        """Register callback for the [OFFER ASKING PRICE] button."""
        self._on_offer = cb

    def set_confirm_callback(self, cb: Callable[[], None]) -> None:
        """Register callback for the [CONFIRM TRADE] button."""
        self._on_confirm = cb

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route MOUSEBUTTONDOWN events to the correct button callback."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._btn_offer_rect and self._btn_offer_rect.collidepoint(event.pos):
            if self._on_offer:
                self._on_offer()
        elif self._btn_confirm_rect and self._btn_confirm_rect.collidepoint(event.pos):
            if self._on_confirm:
                self._on_confirm()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the trade card (or empty-state prompt) onto surface."""
        pygame.draw.rect(surface, _CLR_BG, rect)
        self._btn_offer_rect = None
        self._btn_confirm_rect = None
        if not self._state:
            self._draw_empty(surface, rect)
        else:
            self._draw_card(surface, rect)

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        lines = ["No active trade.", 'Say "I\'d like to trade."']
        lh = self._font_body.get_linesize()
        y = rect.centery - (len(lines) * lh) // 2
        for line in lines:
            txt = self._font_body.render(line, True, _CLR_AMBER)
            surface.blit(txt, (rect.centerx - txt.get_width() // 2, y))
            y += lh

    def _draw_card(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        s = self._state
        x = rect.x + _PAD
        y = rect.y + _PAD

        # Item name header
        item_name = s.get("item_id", "Unknown item")
        title = self._font_body.render(item_name, True, _CLR_AMBER)
        surface.blit(title, (x, y))
        y += title.get_height() + 6

        # NPC purse
        if self._npc_gold is not None:
            purse = self._font_label.render(f"Seller's purse: {self._npc_gold} gold", True, _CLR_GREY)
            surface.blit(purse, (x, y))
            y += purse.get_height() + 4

        # Price row
        center = s.get("center_price", 0)
        threshold = s.get("threshold", center)
        band = s.get("accumulated_band", 0.0)
        price_line = f"Asking: {threshold} gold  (fair: {center}, band: {band:+.0%})"
        pt = self._font_label.render(price_line, True, _CLR_WHITE)
        surface.blit(pt, (x, y))
        y += pt.get_height() + 4

        # Current offer
        offer = s.get("current_offer")
        if offer is not None:
            ot = self._font_label.render(f"Your offer: {offer} gold", True, _CLR_GREEN)
            surface.blit(ot, (x, y))
            y += ot.get_height() + 4

        # Move history
        moves = s.get("moves", [])
        if moves:
            y += 4
            for mv in moves[-4:]:  # last 4 moves
                clr = _CLR_GREEN if mv.get("accepted") else _CLR_RED
                label = f"  {mv['kind']}({mv['value']}) — {'✓' if mv['accepted'] else '✗'}"
                mt = self._font_label.render(label, True, clr)
                surface.blit(mt, (x, y))
                y += mt.get_height() + 2

        # Status badge
        y += 6
        status = s.get("status", "open")
        badge_clr = {
            "open": _CLR_GREY,
            "pending_confirm": _CLR_AMBER,
            "accepted": _CLR_GREEN,
            "declined": _CLR_RED,
        }.get(status, _CLR_GREY)
        badge = self._font_label.render(status.upper(), True, badge_clr)
        surface.blit(badge, (x, y))
        y += badge.get_height() + 10

        # Action buttons
        btn_w = rect.width - _PAD * 2
        if status == "open":
            self._btn_offer_rect = self._draw_button(
                surface, pygame.Rect(x, y, btn_w, _BTN_H),
                "OFFER ASKING PRICE", _CLR_AMBER,
            )
        elif status == "pending_confirm":
            self._btn_confirm_rect = self._draw_button(
                surface, pygame.Rect(x, y, btn_w, _BTN_H),
                "CONFIRM TRADE", _CLR_GREEN,
            )
        elif status == "accepted":
            is_deferred = any(m.get("kind") == "defer_payment" for m in moves)
            msg = "DEFERRED — debt recorded" if is_deferred else "TRADE COMPLETE"
            done = self._font_label.render(msg, True, _CLR_GREEN)
            surface.blit(done, (x, y))

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        colour: tuple[int, int, int],
    ) -> pygame.Rect:
        pygame.draw.rect(surface, _CLR_BG, rect)
        pygame.draw.rect(surface, colour, rect, 1)
        txt = self._font_label.render(label, True, colour)
        surface.blit(txt, (
            rect.centerx - txt.get_width() // 2,
            rect.centery - txt.get_height() // 2,
        ))
        return rect
