"""
Module: quest_panel
Layer: demo_game.ui
Purpose: Renders a single quest card in the PLAYER STATUS right panel.
         Shows an empty-state prompt when no quest has been seeded.
Dependencies: pygame, demo_game.ui.widgets
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE
from demo_game.ui.widgets import _wrap_text

_CLR_BG    = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY  = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]

_ACCEPT_BTN_H = 28


class QuestPanelWidget:
    """Renders a quest card for the PLAYER STATUS tab.

    Displays an empty-state message when quest_data is None (quest engine
    not seeded). When data is present, renders title, word-wrapped description,
    a status badge, and — when status is ``"offered"`` — an [ACCEPT QUEST]
    button that fires the registered callback.

    Args:
        font_body: 14px monospace font for description text.
        font_label: 12px monospace font for the status badge and button.
        quest_data: Quest dict from the engine, or None if no quest is seeded.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
        quest_data: dict | None = None,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._quest_data = quest_data
        self._status_override: str | None = None
        self._on_accept: Callable[[], None] | None = None
        self._accept_rect: pygame.Rect | None = None

    def set_quest(self, data: dict | None) -> None:
        """Update the quest data rendered in this panel."""
        self._quest_data = data
        self._status_override = None

    def set_status(self, status: str) -> None:
        """Override the displayed status without replacing the full quest dict.

        Useful after a lifecycle call (offer/accept) to reflect the new state
        without a round-trip to fetch the updated quest.

        Args:
            status: New status string (e.g. ``"offered"``, ``"active"``).
        """
        self._status_override = status

    def set_accept_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when the [ACCEPT QUEST] button is clicked.

        Args:
            cb: Zero-argument callable; called on the render thread when the
                player clicks the accept button.
        """
        self._on_accept = cb

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the quest card (or empty-state message) onto surface within rect."""
        pygame.draw.rect(surface, _CLR_BG, rect)
        if not self._quest_data:
            self._draw_empty(surface, rect)
        else:
            self._draw_card(surface, rect)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route MOUSEBUTTONDOWN events to the accept button if it is visible."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._accept_rect and self._accept_rect.collidepoint(event.pos):
            if self._on_accept is not None:
                self._on_accept()

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        lines = ["No quests seeded.", "Run: make demo-seed"]
        line_h = self._font_body.get_linesize()
        y = rect.centery - (len(lines) * line_h) // 2
        for line in lines:
            txt = self._font_body.render(line, True, _CLR_AMBER)
            surface.blit(txt, (rect.centerx - txt.get_width() // 2, y))
            y += line_h

    def _draw_card(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x, y = rect.x + 12, rect.y + 12

        title = self._quest_data.get("title", "Quest")
        title_surf = self._font_body.render(title, True, _CLR_AMBER)
        surface.blit(title_surf, (x, y))
        y += title_surf.get_height() + 8

        description = self._quest_data.get("description", "")
        max_w = rect.width - 24
        for line in _wrap_text(self._font_body, description, max_w):
            txt = self._font_body.render(line, True, _CLR_WHITE)
            surface.blit(txt, (x, y))
            y += txt.get_height() + 2

        y += 4
        status = self._status_override or self._quest_data.get("status", "unknown")
        badge = self._font_label.render(status.upper(), True, _CLR_GREY)
        surface.blit(badge, (x, y))
        y += badge.get_height() + 8

        if status == "offered":
            btn_rect = pygame.Rect(x, y, rect.width - 24, _ACCEPT_BTN_H)
            pygame.draw.rect(surface, _CLR_BG, btn_rect)
            pygame.draw.rect(surface, _CLR_AMBER, btn_rect, 1)
            label = self._font_label.render("ACCEPT QUEST", True, _CLR_GREEN)
            surface.blit(
                label,
                (btn_rect.centerx - label.get_width() // 2,
                 btn_rect.centery - label.get_height() // 2),
            )
            self._accept_rect = btn_rect
        else:
            self._accept_rect = None
