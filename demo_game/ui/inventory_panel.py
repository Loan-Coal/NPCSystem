"""
Module: inventory_panel
Layer: demo_game.ui
Purpose: Renders the player's item inventory in the INVENTORY right panel tab.
         Read-only — no buttons. Shows empty-state when no items are held.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

_CLR_BG    = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY  = PALETTE["grey"]

_PAD = 10
_ROW_H = 22


class InventoryPanelWidget:
    """Renders a read-only list of items owned by the player.

    Displays up to 8 items with name, type, and value. Shows an empty-state
    prompt when the inventory is empty.

    Args:
        font_body: Pygame font for item rows.
        font_label: Pygame font for the section header.
    """

    def __init__(self, font_body: pygame.font.Font, font_label: pygame.font.Font) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._items: list[dict] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_items(self, items: list[dict]) -> None:
        """Replace the displayed item list.

        Args:
            items: List of item property dicts from the /v1/admin/items endpoint.
        """
        self._items = items or []

    def get_items(self) -> list[dict]:
        """Return the current item list."""
        return self._items

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the inventory list onto surface within rect."""
        pygame.draw.rect(surface, _CLR_BG, rect)
        if not self._items:
            self._draw_empty(surface, rect)
        else:
            self._draw_list(surface, rect)

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        lines = ["No items in inventory."]
        lh = self._font_body.get_linesize()
        y = rect.centery - (len(lines) * lh) // 2
        for line in lines:
            txt = self._font_body.render(line, True, _CLR_AMBER)
            surface.blit(txt, (rect.centerx - txt.get_width() // 2, y))
            y += lh

    def _draw_list(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x = rect.x + _PAD
        y = rect.y + _PAD

        header = self._font_label.render("INVENTORY", True, _CLR_AMBER)
        surface.blit(header, (x, y))
        y += header.get_height() + 6

        for item in self._items[:8]:
            name = str(item.get("name") or item.get("id") or "Unknown")
            item_type = str(item.get("type") or item.get("item_type") or "")
            value = item.get("value", 0)

            right_label = f"{item_type} — {value} gold" if item_type else f"{value} gold"

            name_surf = self._font_body.render(name, True, _CLR_WHITE)
            right_surf = self._font_body.render(right_label, True, _CLR_GREY)

            surface.blit(name_surf, (x, y))
            right_x = rect.right - _PAD - right_surf.get_width()
            surface.blit(right_surf, (right_x, y))

            y += _ROW_H
            if y + _ROW_H > rect.bottom - _PAD:
                break

        count_text = self._font_label.render(
            f"{len(self._items)} item(s)", True, _CLR_GREY
        )
        surface.blit(count_text, (x, rect.bottom - _PAD - count_text.get_height()))
