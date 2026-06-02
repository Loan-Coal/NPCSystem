"""
Module: actions_panel
Layer: demo_game.ui
Purpose: Scrollable sidebar of contextual action buttons shown in the ACTIONS right-panel tab.
         [Generate Quest], [Inspect], and [Give item] are enabled when an NPC is selected;
         remaining buttons are Phase 4 stubs rendered disabled.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE

# Button geometry constants.
_BTN_H = 40
_BTN_GAP = 6
_BTN_PAD_X = 8
_BTN_MARGIN = 8

# (label, interactive) — False means disabled/stub button.
_ACTIONS: list[tuple[str, bool]] = [
    ("Generate Quest", True),
    ("Inspect",        True),
    ("Give item",      True),
    ("Travel",         True),
    ("Bribe",          True),
]

_INDEX_GENERATE_QUEST = 0
_INDEX_INSPECT = 1
_INDEX_GIVE_ITEM = 2
_INDEX_TRAVEL = 3
_INDEX_BRIBE = 4

_CLR_BG      = PALETTE["bg"]
_CLR_AMBER   = PALETTE["amber"]
_CLR_GREY    = PALETTE["grey"]
_CLR_WHITE   = PALETTE["white"]
_CLR_BORDER  = PALETTE["border"]
_CLR_GREEN   = PALETTE["green"]

_STUB_SUFFIX = " [stub]"


class ActionsPanelWidget:
    """Scrollable list of contextual action buttons for the ACTIONS tab.

    [Generate Quest], [Inspect], [Give item], [Travel], and [Bribe] fire their
    respective callbacks when an NPC is selected.

    Args:
        font: Monospace font for button label text.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self._font = font
        self._npc_selected: bool = False
        self._on_generate_quest: Callable[[], None] | None = None
        self._on_inspect: Callable[[], None] | None = None
        self._on_give_item: Callable[[], None] | None = None
        self._on_travel: Callable[[], None] | None = None
        self._on_bribe: Callable[[], None] | None = None
        self._scroll_y: int = 0
        self._btn_rects: list[pygame.Rect] = []

    def set_npc_selected(self, selected: bool) -> None:
        """Enable or disable NPC-dependent buttons based on selection state."""
        self._npc_selected = selected

    def set_generate_quest_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Generate Quest] is clicked."""
        self._on_generate_quest = cb

    def set_inspect_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Inspect] is clicked."""
        self._on_inspect = cb

    def set_give_item_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Give item] is clicked."""
        self._on_give_item = cb

    def set_travel_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Travel] is clicked."""
        self._on_travel = cb

    def set_bribe_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Bribe] is clicked."""
        self._on_bribe = cb

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route MOUSEBUTTONDOWN and MOUSEWHEEL events to action buttons.

        Only interactive buttons with NPC selected are activated.
        """
        if event.type == pygame.MOUSEWHEEL:
            total_h = len(_ACTIONS) * (_BTN_H + _BTN_GAP)
            self._scroll_y = max(0, min(self._scroll_y - event.y * 20, total_h))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._btn_rects):
                if not rect.collidepoint(event.pos):
                    continue
                if not self._npc_selected:
                    continue
                if i == _INDEX_GENERATE_QUEST and self._on_generate_quest is not None:
                    self._on_generate_quest()
                elif i == _INDEX_INSPECT and self._on_inspect is not None:
                    self._on_inspect()
                elif i == _INDEX_GIVE_ITEM and self._on_give_item is not None:
                    self._on_give_item()
                elif i == _INDEX_TRAVEL and self._on_travel is not None:
                    self._on_travel()
                elif i == _INDEX_BRIBE and self._on_bribe is not None:
                    self._on_bribe()

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw all action buttons within rect, applying the current scroll offset.

        Args:
            surface: Target surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        y = rect.y + _BTN_GAP - self._scroll_y
        self._btn_rects = []
        for i, (label, interactive) in enumerate(_ACTIONS):
            btn_rect = pygame.Rect(
                rect.x + _BTN_MARGIN,
                y,
                rect.width - _BTN_MARGIN * 2,
                _BTN_H,
            )
            self._btn_rects.append(btn_rect)
            enabled = interactive and self._npc_selected
            self._draw_button(surface, btn_rect, label, enabled)
            y += _BTN_H + _BTN_GAP

    def _draw_button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        enabled: bool,
    ) -> None:
        """Draw a single action button."""
        border_clr = _CLR_AMBER if enabled else _CLR_BORDER
        text_clr = _CLR_WHITE if enabled else _CLR_GREY
        pygame.draw.rect(surface, _CLR_BG, rect)
        pygame.draw.rect(surface, border_clr, rect, 1)
        display = label if enabled else label + _STUB_SUFFIX
        txt = self._font.render(display, True, text_clr)
        surface.blit(txt, (rect.x + _BTN_PAD_X, rect.centery - txt.get_height() // 2))
