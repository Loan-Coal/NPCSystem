"""
Module: faction_board
Layer: demo_game.ui
Purpose: FACTION right-panel tab — displays faction-vs-faction standing pairs
         sourced from the engine's factions API. Data pushed from game_window
         via RightPanelRenderer.set_faction_standings(). Render-on-demand only;
         no live poller (slice 2 concern).
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

# ---------------------------------------------------------------------------
# Colour aliases
# ---------------------------------------------------------------------------

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_BORDER = PALETTE["border"]

_CLR_MUTED = (100, 100, 120)
_CLR_NO_DATA = (80, 80, 100)
_CLR_LABEL = PALETTE["amber"]
_CLR_POSITIVE = (100, 200, 120)
_CLR_NEGATIVE = (200, 100, 100)
_CLR_NEUTRAL = (160, 160, 180)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

_PAD_X = 12
_PAD_Y = 12
_ROW_H = 40         # approximate height per faction standing row
_STANDING_COL = 280  # x offset for standing value column

_SECTION_HDR = "FACTION STANDINGS"
_EMPTY_HINT = "No faction data — select an NPC and open FACTION tab to load"


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class FactionBoardWidget:
    """Panel showing faction-vs-faction standing pairs.

    Data is pushed via ``set_standings()``. Renders one row per entry
    showing faction name and standing value with colour coding.
    Gracefully shows an empty-state hint when no data exists.

    Args:
        font_body: Body font used for section header.
        font_label: Smaller monospace font for per-row data.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._standings: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_standings(self, standings: list[dict] | None) -> None:
        """Replace the displayed faction standings.

        Args:
            standings: List of dicts, each with at minimum ``faction_id``,
                       ``faction_name``, and ``standing`` keys. Pass None
                       or [] to clear.
        """
        if not standings:
            self._standings = []
            return
        self._standings = list(standings)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the faction board inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        y = self._draw_section_header(surface, x, y)
        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if not self._standings:
            _draw_no_data(surface, self._font_label, _EMPTY_HINT, _CLR_NO_DATA, rect)
            return

        for entry in self._standings:
            if y + _ROW_H > rect.bottom:
                break
            y = self._draw_standing_row(surface, x, y, rect, entry)
            pygame.draw.line(
                surface, _CLR_BORDER,
                (rect.x + _PAD_X, y - 2), (rect.right - _PAD_X, y - 2),
            )

    def _draw_section_header(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
    ) -> int:
        """Draw the section title; return y below."""
        hdr_surf = self._font_body.render(_SECTION_HDR, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        return y + hdr_surf.get_height() + 6

    def _draw_standing_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        rect: pygame.Rect,
        entry: dict,
    ) -> int:
        """Draw one faction standing row; return y below the row.

        Args:
            surface: Target surface.
            x: Left x coordinate.
            y: Top y coordinate for this row.
            rect: Panel content rect (used for column offset clamping).
            entry: Dict with faction_name and standing keys.
        """
        name = str(entry.get("faction_name") or entry.get("faction_id") or "")
        standing = entry.get("standing")
        standing_val = int(standing) if standing is not None else 0

        name_surf = self._font_label.render(name, True, _CLR_LABEL)
        surface.blit(name_surf, (x, y + 4))

        standing_clr = _standing_colour(standing_val)
        sign = "+" if standing_val > 0 else ""
        standing_text = f"{sign}{standing_val}"
        val_surf = self._font_label.render(standing_text, True, standing_clr)
        col_x = min(rect.x + _STANDING_COL, rect.right - val_surf.get_width() - _PAD_X)
        surface.blit(val_surf, (col_x, y + 4))

        return y + _ROW_H


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _standing_colour(value: int) -> tuple[int, int, int]:
    """Return a colour tuple for a standing value.

    Args:
        value: Standing integer (typically -100 to 100).

    Returns:
        RGB tuple: green for positive, red for negative, grey for zero.
    """
    if value > 0:
        return _CLR_POSITIVE
    if value < 0:
        return _CLR_NEGATIVE
    return _CLR_NEUTRAL


def _draw_no_data(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render hint text word-wrapped and centred inside rect.

    Args:
        surface: Target pygame surface.
        font: Font used for rendering.
        text: Hint text to display.
        clr: Text colour tuple.
        rect: Bounding rect to centre text within.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= rect.width - 2 * _PAD_X:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    total_h = len(lines) * font.get_linesize()
    start_y = rect.centery - total_h // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, clr)
        surface.blit(
            surf,
            (rect.centerx - surf.get_width() // 2, start_y + i * font.get_linesize()),
        )
