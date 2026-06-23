"""
Module: test_inventory_panel
Layer: demo_game (tests)
Purpose: Unit tests for InventoryPanelWidget give mode — start/stop, item selection,
         and cancel button routing. No pygame display init required.
Dependencies: demo_game.ui.inventory_panel, unittest.mock, pygame (constants only)
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame.font.Font stand-in."""

    def get_linesize(self) -> int:
        return 16

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 8
        surf.get_height.return_value = 16
        return surf


def _make_widget():
    from demo_game.ui.panels.inventory_panel import InventoryPanelWidget

    font = _MockFont()
    return InventoryPanelWidget(font, font)


def _mouse_event(pos: tuple[int, int]) -> MagicMock:
    """Build a synthetic MOUSEBUTTONDOWN event at pos."""
    ev = MagicMock()
    ev.type = pygame.MOUSEBUTTONDOWN
    ev.button = 1
    ev.pos = pos
    return ev


def _other_event() -> MagicMock:
    """Build a non-mouse event."""
    ev = MagicMock()
    ev.type = pygame.KEYDOWN
    ev.button = 0
    return ev


# ---------------------------------------------------------------------------
# start_give_mode / stop_give_mode state
# ---------------------------------------------------------------------------


def test_give_mode_initially_false() -> None:
    widget = _make_widget()
    assert widget._give_mode is False


def test_start_give_mode_sets_flag() -> None:
    widget = _make_widget()
    widget.start_give_mode(MagicMock(), MagicMock())
    assert widget._give_mode is True


def test_stop_give_mode_clears_flag() -> None:
    widget = _make_widget()
    widget.start_give_mode(MagicMock(), MagicMock())
    widget.stop_give_mode()
    assert widget._give_mode is False


def test_stop_give_mode_clears_callbacks() -> None:
    widget = _make_widget()
    widget.start_give_mode(MagicMock(), MagicMock())
    widget.stop_give_mode()
    assert widget._on_item_selected is None
    assert widget._on_give_cancel is None


# ---------------------------------------------------------------------------
# handle_event — item row click
# ---------------------------------------------------------------------------


def test_handle_event_noop_when_not_give_mode() -> None:
    widget = _make_widget()
    on_sel = MagicMock()
    # set up row rects manually as if draw() ran, but give mode is off
    item = {"id": "sword_01", "name": "Sword"}
    widget._row_rects = [(pygame.Rect(10, 10, 100, 32), item)]
    widget.handle_event(_mouse_event((50, 20)))
    on_sel.assert_not_called()


def test_handle_event_calls_on_selected_when_row_clicked() -> None:
    widget = _make_widget()
    on_sel = MagicMock()
    widget.start_give_mode(on_sel, MagicMock())
    item = {"id": "spice_01", "name": "Spice Bundle"}
    widget._row_rects = [(pygame.Rect(10, 10, 200, 32), item)]
    widget.handle_event(_mouse_event((50, 20)))
    on_sel.assert_called_once_with(item)


def test_handle_event_calls_correct_item_when_multiple_rows() -> None:
    widget = _make_widget()
    on_sel = MagicMock()
    widget.start_give_mode(on_sel, MagicMock())
    item_a = {"id": "a", "name": "A"}
    item_b = {"id": "b", "name": "B"}
    widget._row_rects = [
        (pygame.Rect(10, 10, 200, 32), item_a),
        (pygame.Rect(10, 50, 200, 32), item_b),
    ]
    widget.handle_event(_mouse_event((50, 60)))
    on_sel.assert_called_once_with(item_b)


def test_handle_event_ignores_non_mouse_events() -> None:
    widget = _make_widget()
    on_sel = MagicMock()
    widget.start_give_mode(on_sel, MagicMock())
    item = {"id": "x", "name": "X"}
    widget._row_rects = [(pygame.Rect(0, 0, 200, 32), item)]
    widget.handle_event(_other_event())
    on_sel.assert_not_called()


# ---------------------------------------------------------------------------
# handle_event — cancel button click
# ---------------------------------------------------------------------------


def test_handle_event_calls_on_cancel_when_cancel_clicked() -> None:
    widget = _make_widget()
    on_cancel = MagicMock()
    widget.start_give_mode(MagicMock(), on_cancel)
    widget._cancel_rect = pygame.Rect(10, 200, 200, 32)
    widget.handle_event(_mouse_event((50, 210)))
    on_cancel.assert_called_once()


def test_handle_event_cancel_noop_when_not_give_mode() -> None:
    widget = _make_widget()
    on_cancel = MagicMock()
    widget._cancel_rect = pygame.Rect(10, 200, 200, 32)
    # give mode is off — cancel click must not fire
    widget.handle_event(_mouse_event((50, 210)))
    on_cancel.assert_not_called()


def test_handle_event_miss_outside_all_rects_fires_nothing() -> None:
    widget = _make_widget()
    on_sel = MagicMock()
    on_cancel = MagicMock()
    widget.start_give_mode(on_sel, on_cancel)
    widget._row_rects = [(pygame.Rect(10, 10, 100, 32), {"id": "x"})]
    widget._cancel_rect = pygame.Rect(10, 200, 100, 32)
    widget.handle_event(_mouse_event((300, 300)))
    on_sel.assert_not_called()
    on_cancel.assert_not_called()
