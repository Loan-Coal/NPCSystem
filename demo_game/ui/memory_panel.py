"""
Module: memory_panel
Layer: demo_game.ui
Purpose: MEMORY right-panel tab — shows the active NPC's Memory nodes with
         content text and a vividness progress bar.
         Data pushed from NpcMemoryPoller via RightPanelRenderer.set_memories().
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
_CLR_VIVID_HIGH = PALETTE["amber"]
_CLR_VIVID_MED = PALETTE["green"]
_CLR_VIVID_LOW = _CLR_GREY

_PAD_X = 12
_PAD_Y = 12
_BAR_H = 8
_MEMORY_BLOCK_H = 56  # approx height per memory block
_MAX_LINE_CHARS = 50  # characters before wrapping to second display line
_VIVIDNESS_MAX = 100

_SECTION_HDR = "MEMORIES"
_HINT = "Talk to NPC then use [Consolidate Memory] to create"
_HISTORICAL_LABEL = "[HISTORICAL]"
_CLR_HISTORICAL = (180, 120, 80)
_CLR_TEMPORAL = (120, 140, 160)


def _vividness_colour(vividness: int) -> tuple[int, int, int]:
    """Return bar colour based on vividness (0=faded, 100=vivid)."""
    if vividness >= 75:
        return _CLR_VIVID_HIGH
    if vividness >= 40:
        return _CLR_VIVID_MED
    return _CLR_VIVID_LOW


def _format_game_time(game_time: object) -> str:
    """Return a compact display string for a game_time dict.

    Args:
        game_time: Expected to be a dict with optional keys year, season,
                   day, time_of_day. Non-dict or None returns empty string.

    Returns:
        Formatted string such as ``"Yr 3 · Winter · Day 12 · night"``
        or ``""`` when game_time is absent/unparseable.
    """
    if not isinstance(game_time, dict):
        return ""
    parts: list[str] = []
    year = game_time.get("year")
    if year is not None:
        parts.append(f"Yr {year}")
    season = game_time.get("season")
    if season:
        parts.append(str(season))
    day = game_time.get("day")
    if day is not None:
        parts.append(f"Day {day}")
    time_of_day = game_time.get("time_of_day")
    if time_of_day:
        parts.append(str(time_of_day))
    return " · ".join(parts)


class MemoryPanelWidget:
    """List of NPC Memory nodes with vividness bar and content text.

    Call ``set_memories()`` after each NpcMemoryPoller tick. Memories are sorted
    descending by vividness so the most vivid memories appear first.

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
        self._memories: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_memories(self, memories: list[dict]) -> None:
        """Replace the displayed memories list.

        Args:
            memories: List of Memory node dicts with at minimum
                      ``content`` and ``vividness`` keys.
        """
        self._memories = sorted(memories, key=lambda m: -int(m.get("vividness", 0)))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the memory panel inside rect.

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

        if not self._memories:
            _draw_no_data(surface, self._font_label, _HINT, _CLR_NO_DATA, rect)
            return

        bar_total_w = rect.width - 2 * _PAD_X
        for memory in self._memories:
            if y + _MEMORY_BLOCK_H > rect.bottom:
                break
            y = self._draw_memory_block(surface, x, y, bar_total_w, memory)
            pygame.draw.line(
                surface, _CLR_BORDER,
                (rect.x + _PAD_X, y - 2), (rect.right - _PAD_X, y - 2),
            )

    def _draw_memory_block(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        memory: dict,
    ) -> int:
        """Draw one memory block; return y below the block."""
        vividness = int(memory.get("vividness", 0))
        content = str(memory.get("content", ""))
        y = self._draw_vividness_row(surface, x, y, total_w, vividness)
        y = self._draw_content_rows(surface, x, y, content)
        y = self._draw_temporal_row(surface, x, y, memory)
        return y + 4

    def _draw_vividness_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        vividness: int,
    ) -> int:
        """Render vividness label and filled bar; return y below the row."""
        bar_clr = _vividness_colour(vividness)
        vivid_lbl = self._font_label.render(f"vividness {vividness}", True, _CLR_MUTED)
        surface.blit(vivid_lbl, (x, y))
        bar_x = x + vivid_lbl.get_width() + 6
        bar_w = total_w - vivid_lbl.get_width() - 6
        bar_rect = pygame.Rect(bar_x, y + 3, max(bar_w, 0), _BAR_H)
        pygame.draw.rect(surface, _CLR_BAR_BG, bar_rect, border_radius=3)
        ratio = max(0.0, min(1.0, vividness / _VIVIDNESS_MAX))
        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            pygame.draw.rect(
                surface, bar_clr,
                pygame.Rect(bar_x, y + 3, filled_w, _BAR_H),
                border_radius=3,
            )
        return y + _BAR_H + 8

    def _draw_content_rows(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        content: str,
    ) -> int:
        """Render up to two display lines of content text; return y below."""
        first_line = content[:_MAX_LINE_CHARS]
        remainder = content[_MAX_LINE_CHARS:_MAX_LINE_CHARS * 2]
        if len(content) > _MAX_LINE_CHARS * 2:
            remainder = remainder[:-1] + "…"
        line1_surf = self._font_label.render(first_line, True, _CLR_WHITE)
        surface.blit(line1_surf, (x, y))
        y += line1_surf.get_height() + 2
        if remainder:
            line2_surf = self._font_label.render(remainder, True, _CLR_VALUE)
            surface.blit(line2_surf, (x, y))
            y += line2_surf.get_height() + 2
        else:
            y += 2
        return y

    def _draw_temporal_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        memory: dict,
    ) -> int:
        """Render occurred_at_game_time and historical marker if present.

        Gracefully omits the row when neither field is populated so that
        older cached memories (which lack Phase 26 fields) render without error.

        Args:
            surface: Target pygame surface.
            x: Left edge.
            y: Top of the row.
            memory: Memory dict; may or may not contain temporal keys.

        Returns:
            Updated y below the row (unchanged when nothing was rendered).
        """
        occurred_at = memory.get("occurred_at_game_time")
        is_historical: bool = bool(memory.get("is_historical", False))

        time_str = _format_game_time(occurred_at)
        if not time_str and not is_historical:
            return y

        label_parts: list[str] = []
        if time_str:
            label_parts.append(time_str)
        if is_historical:
            label_parts.append(_HISTORICAL_LABEL)

        label = "  ".join(label_parts)
        clr = _CLR_HISTORICAL if is_historical else _CLR_TEMPORAL
        lbl_surf = self._font_label.render(label, True, clr)
        surface.blit(lbl_surf, (x, y))
        return y + lbl_surf.get_height() + 2


def _draw_no_data(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render hint text centered inside rect, wrapping at word boundaries."""
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
        surface.blit(surf, (rect.centerx - surf.get_width() // 2, start_y + i * font.get_linesize()))
