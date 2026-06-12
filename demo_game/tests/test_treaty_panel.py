"""
Module: test_treaty_panel
Layer: demo_game (tests)
Purpose: Unit tests for TreatyPanelWidget — headless pygame surface creation.
         No network calls.
Dependencies: demo_game.ui.treaty_panel, pygame, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame
import pytest

from demo_game.ui.treaty_panel import TreatyPanelWidget


@pytest.fixture(autouse=True)
def _init_pygame() -> None:
    """Ensure pygame is initialised for headless surface creation."""
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


def _make_panel() -> TreatyPanelWidget:
    font = pygame.font.SysFont(None, 14)
    return TreatyPanelWidget(font, font)


def _make_surface() -> tuple[pygame.Surface, pygame.Rect]:
    surf = pygame.Surface((320, 480))
    rect = pygame.Rect(0, 0, 320, 480)
    return surf, rect


_SAMPLE_TREATIES = [
    {
        "id": "treaty_001",
        "parties": ["merchants_guild", "city_guard"],
        "terms_narrative": "Non-aggression pact in the market square.",
        "signed_at_tick": 5,
    },
    {
        "id": "treaty_002",
        "parties": ["thieves_guild", "merchants_guild"],
        "terms_narrative": "Smuggling tribute in exchange for safe passage.",
        "signed_at_tick": 8,
    },
]


class TestTreatyPanelInitialState:
    def test_initial_treaties_empty(self) -> None:
        """Widget holds no treaties on construction."""
        panel = _make_panel()
        assert panel._treaties == []

    def test_initial_callbacks_none(self) -> None:
        """Callbacks are None before registration."""
        panel = _make_panel()
        assert panel._broker_cb is None
        assert panel._break_cb is None


class TestTreatyPanelDataSetters:
    def test_set_treaties_stores_copy(self) -> None:
        """set_treaties stores a copy of the supplied list."""
        panel = _make_panel()
        original = list(_SAMPLE_TREATIES)
        panel.set_treaties(original)
        original.append({"extra": True})
        assert len(panel._treaties) == len(_SAMPLE_TREATIES)

    def test_set_broker_callback_stores(self) -> None:
        """set_broker_callback stores the callable."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_broker_callback(cb)
        assert panel._broker_cb is cb

    def test_set_break_callback_stores(self) -> None:
        """set_break_callback stores the callable."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_break_callback(cb)
        assert panel._break_cb is cb


class TestTreatyPanelDraw:
    def test_draw_no_treaties_does_not_raise(self) -> None:
        """Drawing with empty treaty list should not raise."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)

    def test_draw_with_treaties_does_not_raise(self) -> None:
        """Drawing with treaty data should not raise."""
        panel = _make_panel()
        panel.set_treaties(_SAMPLE_TREATIES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)

    def test_draw_populates_break_btn_rects(self) -> None:
        """Drawing with treaties populates _break_btn_rects."""
        panel = _make_panel()
        panel.set_treaties(_SAMPLE_TREATIES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)
        assert len(panel._break_btn_rects) > 0

    def test_draw_sets_broker_btn_rect(self) -> None:
        """Drawing sets _broker_btn_rect."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)
        assert panel._broker_btn_rect is not None


class TestTreatyPanelEventHandling:
    def test_broker_callback_invoked_on_click(self) -> None:
        """Clicking [BROKER] fires the broker callback."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)

        broker_cb = MagicMock()
        panel.set_broker_callback(broker_cb)

        if panel._broker_btn_rect:
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": panel._broker_btn_rect.center, "button": 1},
            )
            panel.handle_event(event)
            broker_cb.assert_called_once()

    def test_break_callback_invoked_on_click(self) -> None:
        """Clicking a [BREAK] button fires the break callback with the treaty dict."""
        panel = _make_panel()
        panel.set_treaties(_SAMPLE_TREATIES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)

        break_cb = MagicMock()
        panel.set_break_callback(break_cb)

        if panel._break_btn_rects:
            btn_rect, treaty = panel._break_btn_rects[0]
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": btn_rect.center, "button": 1},
            )
            panel.handle_event(event)
            break_cb.assert_called_once_with(treaty)

    def test_non_click_event_ignored(self) -> None:
        """Non-MOUSEBUTTONDOWN events do not invoke callbacks."""
        panel = _make_panel()
        broker_cb = MagicMock()
        panel.set_broker_callback(broker_cb)
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_t})
        panel.handle_event(event)
        broker_cb.assert_not_called()

    def test_right_click_ignored(self) -> None:
        """Right-click events (button=3) do not invoke callbacks."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)
        broker_cb = MagicMock()
        panel.set_broker_callback(broker_cb)
        if panel._broker_btn_rect:
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": panel._broker_btn_rect.center, "button": 3},
            )
            panel.handle_event(event)
            broker_cb.assert_not_called()
