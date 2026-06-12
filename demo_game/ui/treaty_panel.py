"""
Module: treaty_panel
Layer: demo_game.ui
Purpose: TREATY right-panel tab — lists active treaties for each demo faction
         and exposes broker/break actions via registered callbacks.
         Data pushed via RightPanelRenderer.set_treaties().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import DEMO_FACTIONS, PALETTE

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]
_CLR_BORDER = PALETTE["border"]

_CLR_MUTED = (100, 100, 120)
_CLR_NO_DATA = (80, 80, 100)
_CLR_VALUE = (180, 180, 200)

_PAD_X = 12
_PAD_Y = 10
_ROW_H = 20
_BTN_H = 22
_BTN_W = 80
_MAX_TERMS_CHARS = 44
_MAX_PARTY_CHARS = 30

_SECTION_HEADER = "FACTION TREATIES"
_BTN_BROKER_LABEL = "[BROKER]"
_BTN_BREAK_LABEL = "[BREAK]"
_NO_TREATIES_MSG = "No active treaties"

# Demo faction display names for the treaty board.
_FACTION_DISPLAY: dict[str, str] = {
    "merchants_guild": "Merchants",
    "city_guard":      "City Guard",
    "thieves_guild":   "Thieves",
}


class TreatyPanelWidget:
    """Displays active faction treaties and exposes broker/break controls.

    Call ``set_treaties()`` after each poll tick. Register callbacks with
    ``set_broker_callback()`` and ``set_break_callback()``.

    Args:
        font_body: Body font for section header.
        font_label: Smaller font for row content and buttons.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._treaties: list[dict] = []
        self._broker_cb: Callable[[], None] | None = None
        self._break_cb: Callable[[dict], None] | None = None
        self._broker_btn_rect: pygame.Rect | None = None
        self._break_btn_rects: list[tuple[pygame.Rect, dict]] = []

    # ------------------------------------------------------------------
    # Data / callback setters
    # ------------------------------------------------------------------

    def set_treaties(self, treaties: list[dict]) -> None:
        """Replace the displayed treaties list.

        Args:
            treaties: Combined list of treaty dicts from all polled factions.
        """
        self._treaties = list(treaties)

    def set_broker_callback(self, cb: Callable[[], None]) -> None:
        """Register callback invoked when [BROKER] is clicked.

        Args:
            cb: Zero-arg callable.
        """
        self._broker_cb = cb

    def set_break_callback(self, cb: Callable[[dict], None]) -> None:
        """Register callback invoked when [BREAK] is clicked for a treaty.

        Args:
            cb: Called with the treaty dict.
        """
        self._break_cb = cb

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle MOUSEBUTTONDOWN events for button clicks.

        Args:
            event: Pygame event to process.
        """
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        pos = event.pos
        if self._broker_btn_rect and self._broker_btn_rect.collidepoint(pos):
            if self._broker_cb:
                self._broker_cb()
            return
        for rect, treaty in self._break_btn_rects:
            if rect.collidepoint(pos):
                if self._break_cb:
                    self._break_cb(treaty)
                return

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the treaty board inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        self._break_btn_rects = []

        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        hdr_surf = self._font_body.render(_SECTION_HEADER, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 4

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if not self._treaties:
            self._draw_msg(surface, rect, _NO_TREATIES_MSG)
        else:
            for treaty in self._treaties:
                if y + _ROW_H * 2 > rect.bottom - _BTN_H - _PAD_Y * 2:
                    break
                y = self._draw_treaty_block(surface, rect, x, y, treaty)

        y = rect.bottom - _BTN_H - _PAD_Y
        self._broker_btn_rect = self._draw_button(
            surface, x, y, _BTN_W, _BTN_H, _BTN_BROKER_LABEL, _CLR_GREEN
        )

    def _draw_treaty_block(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        x: int,
        y: int,
        treaty: dict,
    ) -> int:
        """Draw one treaty block (parties + terms + break button); return y below."""
        parties = treaty.get("parties") or []
        terms = str(treaty.get("terms_narrative", ""))
        treaty_id = str(treaty.get("id", treaty.get("treaty_id", "")))

        parties_str = " ↔ ".join(
            _FACTION_DISPLAY.get(p, p) for p in parties
        )
        parties_str = parties_str[:_MAX_PARTY_CHARS] + (
            "…" if len(parties_str) > _MAX_PARTY_CHARS else ""
        )
        parties_surf = self._font_label.render(parties_str, True, _CLR_VALUE)
        surface.blit(parties_surf, (x, y))

        btn_x = rect.right - _BTN_W - _PAD_X
        btn_rect = self._draw_button(
            surface, btn_x, y, _BTN_W, _BTN_H, _BTN_BREAK_LABEL, _CLR_RED
        )
        self._break_btn_rects.append((btn_rect, treaty))
        y += _ROW_H

        terms_trunc = terms[:_MAX_TERMS_CHARS] + ("…" if len(terms) > _MAX_TERMS_CHARS else "")
        terms_surf = self._font_label.render(terms_trunc, True, _CLR_MUTED)
        surface.blit(terms_surf, (x + 6, y))
        y += _ROW_H + 4

        id_surf = self._font_label.render(f"id: {treaty_id[:24]}", True, _CLR_GREY)
        surface.blit(id_surf, (x + 6, y))
        y += _ROW_H + 4

        return y

    def _draw_button(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        label: str,
        color: tuple[int, int, int],
    ) -> pygame.Rect:
        """Draw a simple text button; return its rect."""
        btn_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surface, color, btn_rect, border_radius=3)
        lbl_surf = self._font_label.render(label, True, _CLR_BG)
        surface.blit(lbl_surf, (
            btn_rect.centerx - lbl_surf.get_width() // 2,
            btn_rect.centery - lbl_surf.get_height() // 2,
        ))
        return btn_rect

    def _draw_msg(self, surface: pygame.Surface, rect: pygame.Rect, msg: str) -> None:
        """Render a centred informational message."""
        surf = self._font_label.render(msg, True, _CLR_NO_DATA)
        surface.blit(surf, (
            rect.centerx - surf.get_width() // 2,
            rect.centery - surf.get_height() // 2,
        ))
