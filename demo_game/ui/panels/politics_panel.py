"""
Module: politics_panel
Layer: demo_game.ui
Purpose: POLITICS right-panel tab — shows the active NPC's pledges (BOUND_BY) and
         leverage nodes (HAS_LEVERAGE) so the political layer is legible in the demo.
         Data pushed from NpcPoliticsPoller via RightPanelRenderer.set_politics().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

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
_CLR_HELD = PALETTE["amber"]
_CLR_USED = PALETTE["grey"]
_CLR_EXPOSED = PALETTE["red"]

_PAD_X = 12
_PAD_Y = 12
_ROW_H = 18
_MAX_TEXT_CHARS = 52

_SECTION_PLEDGES = "PLEDGES"
_SECTION_LEVERAGE = "LEVERAGE"


def _leverage_status_colour(status: str | None) -> tuple[int, int, int]:
    """Return display colour for a leverage status string."""
    if status == "used":
        return _CLR_USED
    if status == "exposed":
        return _CLR_EXPOSED
    return _CLR_HELD


class PoliticsPanelWidget:
    """Displays the active NPC's pledges and leverage in a two-section layout.

    Call ``set_politics(pledges, leverage)`` after each NpcPoliticsPoller tick.

    Args:
        font_body: Body font for section headers.
        font_label: Smaller font for row content.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._pledges: list[dict] = []
        self._leverage: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_politics(self, pledges: list[dict], leverage: list[dict]) -> None:
        """Replace the displayed pledges and leverage lists.

        Args:
            pledges: List of pledge dicts with pledgee_id and pledge_type.
            leverage: List of Leverage node dicts with demand and status.
        """
        self._pledges = list(pledges)
        self._leverage = list(leverage)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render pledges + leverage inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        y = self._draw_section_header(surface, x, y, rect, _SECTION_PLEDGES)
        if not self._pledges:
            no_data_surf = self._font_label.render("No pledges", True, _CLR_NO_DATA)
            surface.blit(no_data_surf, (x, y))
            y += _ROW_H + 4
        else:
            for pledge in self._pledges:
                if y + _ROW_H > rect.bottom:
                    break
                y = self._draw_pledge_row(surface, x, y, rect.width - 2 * _PAD_X, pledge)

        y += 8
        y = self._draw_section_header(surface, x, y, rect, _SECTION_LEVERAGE)
        if not self._leverage:
            no_data_surf = self._font_label.render("No leverage held", True, _CLR_NO_DATA)
            surface.blit(no_data_surf, (x, y))
        else:
            for lv in self._leverage:
                if y + _ROW_H * 2 > rect.bottom:
                    break
                y = self._draw_leverage_block(surface, x, y, rect.width - 2 * _PAD_X, lv)

    def _draw_section_header(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        rect: pygame.Rect,
        title: str,
    ) -> int:
        """Draw a section header with underline; return y below it."""
        hdr_surf = self._font_body.render(title, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 4
        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 6
        return y

    def _draw_pledge_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        pledge: dict,
    ) -> int:
        """Draw one pledge row; return y below it."""
        pledgee = str(pledge.get("pledgee_id", ""))
        pledge_type = str(pledge.get("pledge_type", ""))
        label = f"{pledge_type}  →  {pledgee}"
        truncated = label[:_MAX_TEXT_CHARS] + ("…" if len(label) > _MAX_TEXT_CHARS else "")
        row_surf = self._font_label.render(truncated, True, _CLR_VALUE)
        surface.blit(row_surf, (x, y))
        y += _ROW_H
        return y

    def _draw_leverage_block(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        lv: dict,
    ) -> int:
        """Draw one leverage block (status badge + demand); return y below it."""
        status = str(lv.get("status", "held"))
        demand = str(lv.get("demand", ""))
        status_clr = _leverage_status_colour(status)

        status_surf = self._font_label.render(f"[{status}]", True, status_clr)
        surface.blit(status_surf, (x, y))
        y += _ROW_H

        truncated = demand[:_MAX_TEXT_CHARS] + ("…" if len(demand) > _MAX_TEXT_CHARS else "")
        demand_surf = self._font_label.render(truncated, True, _CLR_MUTED)
        surface.blit(demand_surf, (x + 8, y))
        y += _ROW_H + 6
        return y
