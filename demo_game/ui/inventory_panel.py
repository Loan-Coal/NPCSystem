"""
Module: inventory_panel
Layer: demo_game.ui
Purpose: Renders the player's item inventory in the INVENTORY right panel tab.
         Supports a give mode where rows become clickable for item selection.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE

_CLR_BG    = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY  = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]

_PAD = 10
_ROW_H = 22
_GIVE_ROW_H = 32
_GIVE_BTN_H = 32


class InventoryPanelWidget:
    """Renders a read-only list of items owned by the player.

    Displays up to 8 items with name, type, and value. Shows an empty-state
    prompt when the inventory is empty.

    In give mode (activated via start_give_mode), rows become clickable and a
    Cancel button appears at the bottom. Clicking a row fires on_item_selected;
    clicking Cancel fires on_give_cancel.

    Args:
        font_body: Pygame font for item rows.
        font_label: Pygame font for the section header.
    """

    def __init__(self, font_body: pygame.font.Font, font_label: pygame.font.Font) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._items: list[dict] = []
        self._gold: int | None = None
        self._give_mode: bool = False
        self._on_item_selected: Callable[[dict], None] | None = None
        self._on_give_cancel: Callable[[], None] | None = None
        self._row_rects: list[tuple[pygame.Rect, dict]] = []
        self._cancel_rect: pygame.Rect | None = None

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

    def set_gold(self, gold: int | None) -> None:
        """Set the player's currency balance to display above the item list."""
        self._gold = gold

    def start_give_mode(
        self,
        on_selected: Callable[[dict], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Enter give mode — rows become clickable, a Cancel button appears.

        Args:
            on_selected: Called with the chosen item dict when a row is clicked.
            on_cancel: Called when the Cancel button is clicked.
        """
        self._give_mode = True
        self._on_item_selected = on_selected
        self._on_give_cancel = on_cancel

    def stop_give_mode(self) -> None:
        """Exit give mode and clear callbacks."""
        self._give_mode = False
        self._on_item_selected = None
        self._on_give_cancel = None

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route MOUSEBUTTONDOWN to item rows or the Cancel button in give mode.

        No-op when not in give mode.
        """
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if not self._give_mode:
            return
        for row_rect, item in self._row_rects:
            if row_rect.collidepoint(event.pos):
                if self._on_item_selected:
                    self._on_item_selected(item)
                return
        if self._cancel_rect and self._cancel_rect.collidepoint(event.pos):
            if self._on_give_cancel:
                self._on_give_cancel()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the inventory list onto surface within rect."""
        pygame.draw.rect(surface, _CLR_BG, rect)
        if self._give_mode:
            self._draw_give_list(surface, rect)
        elif not self._items:
            self._draw_empty(surface, rect)
        else:
            self._draw_list(surface, rect)

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x = rect.x + _PAD
        y = rect.y + _PAD
        self._draw_gold_line(surface, x, y)
        lh = self._font_body.get_linesize()
        cy = rect.centery - lh // 2
        txt = self._font_body.render("No items in inventory.", True, _CLR_AMBER)
        surface.blit(txt, (rect.centerx - txt.get_width() // 2, cy))

    def _draw_gold_line(self, surface: pygame.Surface, x: int, y: int) -> None:
        if self._gold is None:
            return
        gold_surf = self._font_label.render(f"Gold: {self._gold}", True, _CLR_AMBER)
        surface.blit(gold_surf, (x, y))

    def _draw_list(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x = rect.x + _PAD
        y = rect.y + _PAD

        header = self._font_label.render("INVENTORY", True, _CLR_AMBER)
        surface.blit(header, (x, y))
        y += header.get_height() + 6

        self._draw_gold_line(surface, x, y)
        if self._gold is not None:
            y += self._font_label.get_linesize() + 4

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

    def _draw_give_list(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw clickable item rows and a Cancel button for give mode."""
        self._row_rects = []
        self._cancel_rect = None

        x = rect.x + _PAD
        y = rect.y + _PAD

        header = self._font_label.render("SELECT ITEM TO GIVE", True, _CLR_AMBER)
        surface.blit(header, (x, y))
        y += header.get_height() + 8

        cancel_reserved = _GIVE_BTN_H + _PAD * 2
        max_y = rect.bottom - cancel_reserved

        if not self._items:
            empty = self._font_body.render("No items in inventory.", True, _CLR_GREY)
            surface.blit(empty, (x, y))
        else:
            for item in self._items[:8]:
                row_rect = pygame.Rect(
                    rect.x + _PAD, y, rect.width - _PAD * 2, _GIVE_ROW_H
                )
                if y + _GIVE_ROW_H > max_y:
                    break
                pygame.draw.rect(surface, _CLR_BG, row_rect)
                pygame.draw.rect(surface, _CLR_GREEN, row_rect, 1)

                name = str(item.get("name") or item.get("id") or "Unknown")
                value = item.get("value", 0)
                name_surf = self._font_body.render(name, True, _CLR_WHITE)
                val_surf = self._font_body.render(f"{value}g", True, _CLR_GREY)
                row_text_y = row_rect.centery - name_surf.get_height() // 2
                surface.blit(name_surf, (row_rect.x + _PAD, row_text_y))
                surface.blit(val_surf, (row_rect.right - val_surf.get_width() - _PAD, row_text_y))

                self._row_rects.append((row_rect, item))
                y += _GIVE_ROW_H + 4

        cancel_rect = pygame.Rect(
            rect.x + _PAD,
            rect.bottom - _GIVE_BTN_H - _PAD,
            rect.width - _PAD * 2,
            _GIVE_BTN_H,
        )
        pygame.draw.rect(surface, _CLR_BG, cancel_rect)
        pygame.draw.rect(surface, _CLR_AMBER, cancel_rect, 1)
        cancel_txt = self._font_label.render("[Cancel]", True, _CLR_AMBER)
        surface.blit(
            cancel_txt,
            (
                cancel_rect.centerx - cancel_txt.get_width() // 2,
                cancel_rect.centery - cancel_txt.get_height() // 2,
            ),
        )
        self._cancel_rect = cancel_rect
