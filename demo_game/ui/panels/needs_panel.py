"""
Module: needs_panel
Layer: demo_game.ui
Purpose: NEEDS right-panel tab — shows the active NPC's Need nodes with
         kind label, level progress bar, and decay rate.
         Data pushed from NpcNeedsPoller via RightPanelRenderer.set_needs().
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

_CLR_BAR_BG = (40, 40, 55)
_CLR_MUTED = (100, 100, 120)
_CLR_VALUE = (180, 180, 200)
_CLR_NO_DATA = (80, 80, 100)
_CLR_CRITICAL = (200, 60, 60)
_CLR_LOW = (200, 140, 60)
_CLR_OK = PALETTE["green"]

_PAD_X = 12
_PAD_Y = 12
_ROW_H = 28          # height per need row
_BAR_H = 12
_KIND_COL_W = 90     # fixed width for kind label
_DECAY_COL_W = 60    # fixed width for decay label at right

_LEVEL_MAX = 100
_LEVEL_CRITICAL_THRESHOLD = 30
_LEVEL_LOW_THRESHOLD = 60

_SECTION_HDR = "NEEDS"


def _level_colour(level: int) -> tuple[int, int, int]:
    """Return bar colour based on need level (0 = critical, 100 = full)."""
    if level <= _LEVEL_CRITICAL_THRESHOLD:
        return _CLR_CRITICAL
    if level <= _LEVEL_LOW_THRESHOLD:
        return _CLR_LOW
    return _CLR_OK


class NeedsPanelWidget:
    """Scrollable list of NPC Need nodes with kind, level bar, and decay rate.

    Call ``set_needs()`` after each NpcNeedsPoller tick. Needs are sorted
    ascending by level so critical needs appear first.

    Args:
        font_body: Body font for the section header.
        font_label: Smaller font for row content.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._needs: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_needs(self, needs: list[dict]) -> None:
        """Replace the displayed needs list.

        Args:
            needs: List of Need node property dicts with at minimum
                   ``kind``, ``level``, and ``decay_rate`` keys.
        """
        self._needs = sorted(needs, key=lambda n: n.get("level", 50))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the needs panel inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        hdr_surf = self._font_body.render(_SECTION_HDR, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 6

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if not self._needs:
            _draw_centered(surface, self._font_label, "No needs data", _CLR_NO_DATA, rect)
            return

        bar_total_w = rect.width - 2 * _PAD_X
        for need in self._needs:
            if y + _ROW_H > rect.bottom:
                break
            y = self._draw_need_row(surface, x, y, bar_total_w, need)

    def _draw_need_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        need: dict,
    ) -> int:
        """Draw one need row; return y below the row."""
        kind = str(need.get("kind", "?")).lower()
        level = int(need.get("level", 50))
        decay = int(need.get("decay_rate", 0))

        bar_clr = _level_colour(level)
        kind_surf = self._font_label.render(kind, True, _CLR_WHITE)
        surface.blit(kind_surf, (x, y + 2))

        decay_str = f"-{decay}/tick"
        decay_surf = self._font_label.render(decay_str, True, _CLR_MUTED)
        decay_x = x + total_w - decay_surf.get_width()
        surface.blit(decay_surf, (decay_x, y + 2))

        bar_x = x + _KIND_COL_W
        bar_w = decay_x - bar_x - 6
        bar_rect = pygame.Rect(bar_x, y + 5, max(bar_w, 0), _BAR_H)
        pygame.draw.rect(surface, _CLR_BAR_BG, bar_rect, border_radius=3)

        ratio = max(0.0, min(1.0, level / _LEVEL_MAX))
        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            pygame.draw.rect(
                surface, bar_clr,
                pygame.Rect(bar_x, y + 5, filled_w, _BAR_H),
                border_radius=3,
            )

        val_surf = self._font_label.render(str(level), True, _CLR_VALUE)
        surface.blit(val_surf, (bar_x + max(bar_w, 0) + 4, y + 2))

        return y + _ROW_H


def _draw_centered(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render text centred inside rect."""
    surf = font.render(text, True, clr)
    surface.blit(surf, (
        rect.centerx - surf.get_width() // 2,
        rect.centery - surf.get_height() // 2,
    ))
