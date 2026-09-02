"""
Module: no_data
Layer: demo_game.ui.widgets
Purpose: The two shared "nothing to show here" renderings, so panels and boards stop
         each carrying their own copy.
Dependencies: pygame.
Used by: ui/boards/faction_board.py, ui/panels/memory_panel.py,
         ui/panels/retrieval_panel.py, ui/panels/player_model_panel.py,
         ui/panels/scheme_board_panel.py.

Five modules defined a private `_draw_no_data`. They were not one helper copied five
times but two helpers copied five times: three byte-identical word-wrapping versions,
and two byte-identical single-line versions. Both are kept, because they render
differently — folding the single-line callers into the wrapping one would move their
text by the difference between `get_linesize()` and `get_height()`. Collapsing them to
one function would be a behaviour change disguised as a cleanup (R4.3).
"""

from __future__ import annotations

import pygame

#: Horizontal padding reserved on each side when wrapping. Every call site defined
#: this as 12 independently; it is one constant now.
PAD_X: int = 12


def draw_wrapped_no_data(
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
    lines = _wrap(text, font, rect.width)
    total_h = len(lines) * font.get_linesize()
    start_y = rect.centery - total_h // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, clr)
        surface.blit(
            surf,
            (rect.centerx - surf.get_width() // 2, start_y + i * font.get_linesize()),
        )


def draw_centered_no_data(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render a single centred line of text, without wrapping.

    Args:
        surface: Target pygame surface.
        font: Font used for rendering.
        text: Message to display.
        clr: Text colour tuple.
        rect: Bounding rect to centre text within.
    """
    surf = font.render(text, True, clr)
    surface.blit(
        surf,
        (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2),
    )


def _wrap(text: str, font: pygame.font.Font, width: int) -> list[str]:
    """Greedily break text into lines that fit within width minus PAD_X either side."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= width - 2 * PAD_X:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
