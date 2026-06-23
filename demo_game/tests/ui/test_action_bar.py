"""
Module: test_action_bar
Layer: demo_game (tests)
Purpose: TDD unit tests for ActionBarWidget — click routing and no-op paths.
         No pygame display init required.
Dependencies: demo_game.ui.action_bar, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from demo_game.ui.widgets.action_bar import ActionBarWidget, _PRESETS


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockFont:
    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)

    def get_linesize(self) -> int:
        return 16

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 8
        surf.get_height.return_value = 16
        return surf


# ---------------------------------------------------------------------------
# handle_event — click routing
# ---------------------------------------------------------------------------


def test_action_bar_click_first_button_returns_preset_text() -> None:
    """Clicking inside the first button rect returns its preset fill text."""
    widget = ActionBarWidget(_MockFont())
    widget._rects = [
        pygame.Rect(0, 0, 100, 28),
        pygame.Rect(100, 0, 100, 28),
        pygame.Rect(200, 0, 100, 28),
    ]
    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (50, 10)  # inside first rect
    assert widget.handle_event(event) == _PRESETS[0][1]


def test_action_bar_click_last_button_returns_its_preset_text() -> None:
    """Clicking the last button returns the last preset fill text."""
    widget = ActionBarWidget(_MockFont())
    widget._rects = [
        pygame.Rect(0, 0, 100, 28),
        pygame.Rect(100, 0, 100, 28),
        pygame.Rect(200, 0, 100, 28),
    ]
    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (250, 10)  # inside third rect
    assert widget.handle_event(event) == _PRESETS[2][1]


def test_action_bar_click_outside_all_rects_returns_none() -> None:
    """A click that misses all buttons returns None."""
    widget = ActionBarWidget(_MockFont())
    widget._rects = [pygame.Rect(0, 0, 100, 28)]
    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (500, 500)
    assert widget.handle_event(event) is None


def test_action_bar_no_rects_returns_none() -> None:
    """Before draw() is called, _rects is empty — any click returns None."""
    widget = ActionBarWidget(_MockFont())
    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (50, 10)
    assert widget.handle_event(event) is None


def test_action_bar_non_click_event_returns_none() -> None:
    """Non-MOUSEBUTTONDOWN events always return None."""
    widget = ActionBarWidget(_MockFont())
    widget._rects = [pygame.Rect(0, 0, 100, 28)]
    event = MagicMock()
    event.type = pygame.KEYDOWN
    assert widget.handle_event(event) is None


# ---------------------------------------------------------------------------
# draw — smoke test (no crash)
# ---------------------------------------------------------------------------


def test_action_bar_draw_no_crash() -> None:
    """draw() must not raise regardless of surface/rect mocks."""
    widget = ActionBarWidget(_MockFont())
    surface = MagicMock()
    with patch("demo_game.ui.widgets.action_bar.pygame") as mock_pygame:
        mock_pygame.MOUSEBUTTONDOWN = pygame.MOUSEBUTTONDOWN
        mock_pygame.mouse.get_pos.return_value = (-1, -1)
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(surface, MagicMock())
