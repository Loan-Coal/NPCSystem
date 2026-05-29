"""
Module: action_bar
Layer: demo_game.ui
Purpose: Three preset dialogue buttons above the input box. Clicking pre-fills
         the input; does NOT auto-submit.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.left_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

_PRESETS: list[tuple[str, str]] = [
    ("Ask about war",  "Tell me about the war in the north."),
    ("Trade",          "I'd like to trade."),
    ("Ask for rumors", "Have you heard any rumors lately?"),
]


class ActionBarWidget:
    """Three preset dialogue buttons rendered side by side.

    Clicking a button pre-fills the dialogue input box with the preset text.
    The player can edit the text before pressing Enter — it does NOT auto-submit.

    Args:
        font: Font for button label text.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self._font = font
        self._rects: list[pygame.Rect] = []

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw three equal-width buttons inside rect."""
        pygame.draw.rect(surface, PALETTE["bg"], rect)
        n = len(_PRESETS)
        btn_w = rect.width // n
        mouse_pos = pygame.mouse.get_pos()
        self._rects = []
        for i, (label, _) in enumerate(_PRESETS):
            btn_rect = pygame.Rect(rect.x + i * btn_w, rect.y, btn_w - 2, rect.height)
            self._rects.append(btn_rect)
            hovered = btn_rect.collidepoint(mouse_pos)
            pygame.draw.rect(surface, PALETTE["amber"] if hovered else PALETTE["border"], btn_rect, 1)
            txt = self._font.render(label, True, PALETTE["amber"] if hovered else PALETTE["grey"])
            surface.blit(
                txt,
                (btn_rect.centerx - txt.get_width() // 2,
                 btn_rect.centery - txt.get_height() // 2),
            )

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Return the preset fill text if a button was clicked, else None."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, btn_rect in enumerate(self._rects):
                if btn_rect.collidepoint(event.pos):
                    return _PRESETS[i][1]
        return None
