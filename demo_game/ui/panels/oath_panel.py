"""
Module: oath_panel
Layer: demo_game.ui
Purpose: OATH right-panel tab — lists the active NPC's pledges and exposes
         swear/break actions via registered callbacks.
         Data pushed via RightPanelRenderer.set_oath_pledges().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE

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
_PAD_Y = 12
_ROW_H = 20
_BTN_H = 22
_BTN_W = 90
_MAX_TEXT_CHARS = 50

_SECTION_OATHS = "ACTIVE OATHS"
_BTN_SWEAR_LABEL = "[SWEAR]"
_BTN_BREAK_LABEL = "[BREAK]"
_NO_DATA_MSG = "No active oaths"
_NO_NPC_MSG = "Select an NPC to view oaths"


class OathPanelWidget:
    """Displays the active NPC's pledges and supports swear/break actions.

    Call ``set_pledges()`` after each PledgePoller tick. Call with an
    empty list to show the "no oaths" placeholder.

    Register callbacks with ``set_swear_callback()`` and
    ``set_break_callback()`` to handle button clicks.

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
        self._pledges: list[dict] = []
        self._npc_id: str | None = None
        self._swear_cb: Callable[[], None] | None = None
        self._break_cb: Callable[[dict], None] | None = None
        # Button rects tracked for click detection
        self._swear_btn_rect: pygame.Rect | None = None
        self._break_btn_rects: list[tuple[pygame.Rect, dict]] = []

    # ------------------------------------------------------------------
    # Data / callback setters
    # ------------------------------------------------------------------

    def set_pledges(self, pledges: list[dict]) -> None:
        """Replace the displayed pledge list.

        Args:
            pledges: List of pledge dicts from PledgePoller.
        """
        self._pledges = list(pledges)

    def set_active_npc(self, npc_id: str | None) -> None:
        """Track the active NPC id (used by swear callback context).

        Args:
            npc_id: Current active NPC id, or None.
        """
        self._npc_id = npc_id

    def set_swear_callback(self, cb: Callable[[], None]) -> None:
        """Register callback invoked when [SWEAR] is clicked.

        Args:
            cb: Zero-arg callable.
        """
        self._swear_cb = cb

    def set_break_callback(self, cb: Callable[[dict], None]) -> None:
        """Register callback invoked when [BREAK] is clicked for a pledge.

        Args:
            cb: Called with the pledge dict of the targeted oath.
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
        if self._swear_btn_rect and self._swear_btn_rect.collidepoint(pos):
            if self._swear_cb:
                self._swear_cb()
            return
        for rect, pledge in self._break_btn_rects:
            if rect.collidepoint(pos):
                if self._break_cb:
                    self._break_cb(pledge)
                return

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the oath panel inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        self._break_btn_rects = []

        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        hdr_surf = self._font_body.render(_SECTION_OATHS, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 4

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if self._npc_id is None:
            self._draw_msg(surface, rect, _NO_NPC_MSG)
            return

        if not self._pledges:
            self._draw_msg(surface, rect, _NO_DATA_MSG)
        else:
            for pledge in self._pledges:
                if y + _ROW_H > rect.bottom - _BTN_H - _PAD_Y * 2:
                    break
                y = self._draw_pledge_row(surface, rect, x, y, pledge)

        y = rect.bottom - _BTN_H - _PAD_Y
        self._swear_btn_rect = self._draw_button(
            surface, x, y, _BTN_W, _BTN_H, _BTN_SWEAR_LABEL, _CLR_GREEN
        )

    def _draw_pledge_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        x: int,
        y: int,
        pledge: dict,
    ) -> int:
        """Draw one pledge row with a BREAK button; return y below the row."""
        pledgee = str(pledge.get("pledgee_id", ""))
        pledge_type = str(pledge.get("pledge_type", ""))
        label = f"{pledge_type}  →  {pledgee}"
        truncated = label[:_MAX_TEXT_CHARS] + ("…" if len(label) > _MAX_TEXT_CHARS else "")
        row_surf = self._font_label.render(truncated, True, _CLR_VALUE)
        surface.blit(row_surf, (x, y))

        btn_x = rect.right - _BTN_W - _PAD_X
        btn_rect = self._draw_button(
            surface, btn_x, y, _BTN_W, _BTN_H, _BTN_BREAK_LABEL, _CLR_RED
        )
        self._break_btn_rects.append((btn_rect, pledge))
        return y + _ROW_H + 2

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
