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
from demo_game.ui.widgets.widgets import _wrap_text

_CLR_BG    = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY  = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]

_ACCEPT_BTN_H = 28


class QuestPanelWidget:
    """Renders a quest card for the PLAYER STATUS tab.

    Displays an empty-state message when quest_data is None (quest engine
    not seeded). When data is present, renders title, description, status badge,
    reward amount, and action buttons:
    - [ACCEPT QUEST] when status is ``"offered"``
    - [COMPLETE QUEST] when status is ``"accepted"`` or ``"in_progress"``
    - [ACCEPT REWARD] when status is ``"completed"`` and rewards not yet applied

    Args:
        font_body: 14px monospace font for description text.
        font_label: 12px monospace font for the status badge and buttons.
        quest_data: Quest state dict from the engine, or None if no quest is seeded.
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
        self._on_complete: Callable[[], None] | None = None
        self._on_reward: Callable[[], None] | None = None
        self._accept_rect: pygame.Rect | None = None
        self._complete_rect: pygame.Rect | None = None
        self._reward_rect: pygame.Rect | None = None

    def set_quest(self, data: dict | None) -> None:
        """Update the quest data rendered in this panel."""
        self._quest_data = data
        self._status_override = None

    def set_status(self, status: str) -> None:
        """Override the displayed status without replacing the full quest dict."""
        self._status_override = status

    def set_accept_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [ACCEPT QUEST] is clicked."""
        self._on_accept = cb

    def set_complete_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [COMPLETE QUEST] is clicked."""
        self._on_complete = cb

    def set_reward_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [ACCEPT REWARD] is clicked."""
        self._on_reward = cb

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the quest card (or empty-state message) onto surface within rect."""
        pygame.draw.rect(surface, _CLR_BG, rect)
        if not self._quest_data:
            self._draw_empty(surface, rect)
        else:
            self._draw_card(surface, rect)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route MOUSEBUTTONDOWN events to action buttons."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._accept_rect and self._accept_rect.collidepoint(event.pos):
            if self._on_accept is not None:
                self._on_accept()
        elif self._complete_rect and self._complete_rect.collidepoint(event.pos):
            if self._on_complete is not None:
                self._on_complete()
        elif self._reward_rect and self._reward_rect.collidepoint(event.pos):
            if self._on_reward is not None:
                self._on_reward()

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        lines = ["No active quest.", "Accept a quest from an NPC."]
        line_h = self._font_body.get_linesize()
        y = rect.centery - (len(lines) * line_h) // 2
        for line in lines:
            txt = self._font_body.render(line, True, _CLR_AMBER)
            surface.blit(txt, (rect.centerx - txt.get_width() // 2, y))
            y += line_h

    def _draw_card(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x, y = rect.x + 12, rect.y + 12
        self._accept_rect = None
        self._complete_rect = None
        self._reward_rect = None

        title = self._quest_data.get("title", "Quest")
        title_surf = self._font_body.render(title, True, _CLR_AMBER)
        surface.blit(title_surf, (x, y))

        source = self._quest_data.get("source")
        badge_label = "[GENERATED]" if source == "generated" else "[SEEDED]"
        badge_clr = _CLR_GREEN if source == "generated" else _CLR_GREY
        badge_surf = self._font_label.render(badge_label, True, badge_clr)
        surface.blit(badge_surf, (x + title_surf.get_width() + 8, y + 2))

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
        y += badge.get_height() + 6

        currency = self._quest_data.get("currency_reward")
        if currency:
            amount = currency.get("amount", 0) if isinstance(currency, dict) else 0
            reward_txt = self._font_label.render(f"Reward: {amount} gold", True, _CLR_GREEN)
            surface.blit(reward_txt, (x, y))
            y += reward_txt.get_height() + 8

        rewards_applied = self._quest_data.get("rewards_applied", False)

        if status == "offered":
            btn_rect = pygame.Rect(x, y, rect.width - 24, _ACCEPT_BTN_H)
            pygame.draw.rect(surface, _CLR_BG, btn_rect)
            pygame.draw.rect(surface, _CLR_AMBER, btn_rect, 1)
            label = self._font_label.render("ACCEPT QUEST", True, _CLR_GREEN)
            surface.blit(label, (btn_rect.centerx - label.get_width() // 2, btn_rect.centery - label.get_height() // 2))
            self._accept_rect = btn_rect
        elif status in {"accepted", "in_progress"}:
            btn_rect = pygame.Rect(x, y, rect.width - 24, _ACCEPT_BTN_H)
            pygame.draw.rect(surface, _CLR_BG, btn_rect)
            pygame.draw.rect(surface, _CLR_AMBER, btn_rect, 1)
            label = self._font_label.render("COMPLETE QUEST", True, _CLR_GREEN)
            surface.blit(label, (btn_rect.centerx - label.get_width() // 2, btn_rect.centery - label.get_height() // 2))
            self._complete_rect = btn_rect
        elif status == "completed" and not rewards_applied:
            btn_rect = pygame.Rect(x, y, rect.width - 24, _ACCEPT_BTN_H)
            pygame.draw.rect(surface, _CLR_BG, btn_rect)
            pygame.draw.rect(surface, _CLR_GREEN, btn_rect, 1)
            label = self._font_label.render("ACCEPT REWARD", True, _CLR_GREEN)
            surface.blit(label, (btn_rect.centerx - label.get_width() // 2, btn_rect.centery - label.get_height() // 2))
            self._reward_rect = btn_rect
