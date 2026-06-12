"""
Module: test_investigation_panel
Layer: demo_game (tests)
Purpose: Unit tests for InvestigationPanelWidget — headless pygame surface creation.
         No network calls.
Dependencies: demo_game.ui.investigation_panel, pygame, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame
import pytest

from demo_game.ui.investigation_panel import InvestigationPanelWidget


@pytest.fixture(autouse=True)
def _init_pygame() -> None:
    """Ensure pygame is initialised for headless surface creation."""
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


def _make_panel() -> InvestigationPanelWidget:
    font = pygame.font.SysFont(None, 14)
    return InvestigationPanelWidget(font, font)


def _make_surface() -> tuple[pygame.Surface, pygame.Rect]:
    surf = pygame.Surface((320, 480))
    rect = pygame.Rect(0, 0, 320, 480)
    return surf, rect


_SAMPLE_INVESTIGATION = {
    "alibi_contradictions": [
        {
            "description": "Witness claims aldric was at the docks",
            "source": "mira_innkeeper",
        },
    ],
    "rumor_contradictions": [
        {
            "description": "Rumor claims the chest was never opened",
            "source": "old_henryk",
        },
    ],
    "evidence": [],
    "witnesses": [],
    "suspects": [],
}


class TestInvestigationPanelInitialState:
    def test_initial_investigation_none(self) -> None:
        """Widget holds no investigation data on construction."""
        panel = _make_panel()
        assert panel._investigation is None

    def test_initial_event_id_none(self) -> None:
        """Event id is None on construction."""
        panel = _make_panel()
        assert panel._event_id is None

    def test_initial_callback_none(self) -> None:
        """Investigate callback is None before registration."""
        panel = _make_panel()
        assert panel._investigate_cb is None


class TestInvestigationPanelDataSetters:
    def test_set_investigation_stores_data(self) -> None:
        """set_investigation stores the supplied dict."""
        panel = _make_panel()
        panel.set_investigation(_SAMPLE_INVESTIGATION)
        assert panel._investigation is _SAMPLE_INVESTIGATION

    def test_set_investigation_none_clears(self) -> None:
        """set_investigation(None) clears the data."""
        panel = _make_panel()
        panel.set_investigation(_SAMPLE_INVESTIGATION)
        panel.set_investigation(None)
        assert panel._investigation is None

    def test_set_investigation_resets_scroll(self) -> None:
        """set_investigation resets scroll position to 0."""
        panel = _make_panel()
        panel._scroll_y = 50
        panel.set_investigation(_SAMPLE_INVESTIGATION)
        assert panel._scroll_y == 0

    def test_set_event_id_stores(self) -> None:
        """set_event_id stores the event id."""
        panel = _make_panel()
        panel.set_event_id("crime_001")
        assert panel._event_id == "crime_001"

    def test_set_investigate_callback_stores(self) -> None:
        """set_investigate_callback stores the callable."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_investigate_callback(cb)
        assert panel._investigate_cb is cb


class TestInvestigationPanelDraw:
    def test_draw_no_data_does_not_raise(self) -> None:
        """Drawing with no investigation data should not raise."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)

    def test_draw_with_investigation_does_not_raise(self) -> None:
        """Drawing with full investigation data should not raise."""
        panel = _make_panel()
        panel.set_investigation(_SAMPLE_INVESTIGATION)
        surf, rect = _make_surface()
        panel.draw(surf, rect)

    def test_draw_empty_contradictions_does_not_raise(self) -> None:
        """Drawing with empty contradiction lists should not raise."""
        panel = _make_panel()
        panel.set_investigation({"alibi_contradictions": [], "rumor_contradictions": []})
        surf, rect = _make_surface()
        panel.draw(surf, rect)

    def test_draw_sets_investigate_btn_rect(self) -> None:
        """Drawing always sets _investigate_btn_rect."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)
        assert panel._investigate_btn_rect is not None


class TestInvestigationPanelEventHandling:
    def test_investigate_callback_invoked_on_click(self) -> None:
        """Clicking [INVESTIGATE] fires the investigate callback."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)

        cb = MagicMock()
        panel.set_investigate_callback(cb)

        if panel._investigate_btn_rect:
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": panel._investigate_btn_rect.center, "button": 1},
            )
            panel.handle_event(event)
            cb.assert_called_once()

    def test_mousewheel_updates_scroll(self) -> None:
        """MOUSEWHEEL event updates scroll_y."""
        panel = _make_panel()
        panel._scroll_y = 40
        event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": -1})
        panel.handle_event(event)
        assert panel._scroll_y == 60  # -= -1 * 20 → += 20

    def test_mousewheel_clamps_to_zero(self) -> None:
        """MOUSEWHEEL cannot scroll above 0."""
        panel = _make_panel()
        panel._scroll_y = 5
        event = pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1})
        panel.handle_event(event)
        assert panel._scroll_y == 0

    def test_non_click_event_ignored(self) -> None:
        """Non-click events do not invoke callback."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_investigate_callback(cb)
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_i})
        panel.handle_event(event)
        cb.assert_not_called()
