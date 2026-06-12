"""
Module: test_oath_panel
Layer: demo_game (tests)
Purpose: Unit tests for OathPanelWidget — headless pygame surface creation.
         No network calls.
Dependencies: demo_game.ui.oath_panel, pygame, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pygame
import pytest

from demo_game.ui.oath_panel import OathPanelWidget


@pytest.fixture(autouse=True)
def _init_pygame() -> None:
    """Ensure pygame is initialised for headless surface creation."""
    pygame.display.init()
    pygame.font.init()
    yield
    pygame.quit()


def _make_panel() -> OathPanelWidget:
    """Construct an OathPanelWidget with minimal fonts."""
    font = pygame.font.SysFont(None, 14)
    return OathPanelWidget(font, font)


def _make_surface() -> tuple[pygame.Surface, pygame.Rect]:
    surf = pygame.Surface((320, 480))
    rect = pygame.Rect(0, 0, 320, 480)
    return surf, rect


_SAMPLE_PLEDGES = [
    {"pledgee_id": "thieves_guild", "pledge_type": "fealty", "tick": 0},
    {"pledgee_id": "mira_innkeeper", "pledge_type": "protect", "tick": 1},
]


class TestOathPanelInitialState:
    def test_initial_pledges_empty(self) -> None:
        """Widget holds no pledges on construction."""
        panel = _make_panel()
        assert panel._pledges == []

    def test_initial_npc_id_none(self) -> None:
        """Active NPC is None on construction."""
        panel = _make_panel()
        assert panel._npc_id is None


class TestOathPanelDataSetters:
    def test_set_pledges_stores_copy(self) -> None:
        """set_pledges stores a copy; mutating the original does not affect panel."""
        panel = _make_panel()
        original = list(_SAMPLE_PLEDGES)
        panel.set_pledges(original)
        original.append({"extra": True})
        assert len(panel._pledges) == len(_SAMPLE_PLEDGES)

    def test_set_active_npc_updates_id(self) -> None:
        """set_active_npc stores the NPC id."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        assert panel._npc_id == "lira_fence"

    def test_set_swear_callback_stores(self) -> None:
        """set_swear_callback stores the callable."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_swear_callback(cb)
        assert panel._swear_cb is cb

    def test_set_break_callback_stores(self) -> None:
        """set_break_callback stores the callable."""
        panel = _make_panel()
        cb = MagicMock()
        panel.set_break_callback(cb)
        assert panel._break_cb is cb


class TestOathPanelDraw:
    def test_draw_no_npc_does_not_raise(self) -> None:
        """Drawing with no NPC selected should not raise."""
        panel = _make_panel()
        surf, rect = _make_surface()
        panel.draw(surf, rect)  # Should not raise

    def test_draw_with_pledges_does_not_raise(self) -> None:
        """Drawing with pledge data should not raise."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        panel.set_pledges(_SAMPLE_PLEDGES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)  # Should not raise

    def test_draw_empty_pledges_does_not_raise(self) -> None:
        """Drawing with an NPC but no pledges should not raise."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        panel.set_pledges([])
        surf, rect = _make_surface()
        panel.draw(surf, rect)  # Should not raise

    def test_draw_populates_break_btn_rects(self) -> None:
        """Drawing with pledges should populate _break_btn_rects."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        panel.set_pledges(_SAMPLE_PLEDGES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)
        assert len(panel._break_btn_rects) == len(_SAMPLE_PLEDGES)


class TestOathPanelEventHandling:
    def test_swear_callback_invoked_on_button_click(self) -> None:
        """Clicking the SWEAR button fires the swear callback."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        panel.set_pledges([])
        surf, rect = _make_surface()
        panel.draw(surf, rect)

        swear_cb = MagicMock()
        panel.set_swear_callback(swear_cb)

        if panel._swear_btn_rect:
            btn = panel._swear_btn_rect
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": btn.center, "button": 1},
            )
            panel.handle_event(event)
            swear_cb.assert_called_once()

    def test_break_callback_invoked_on_break_click(self) -> None:
        """Clicking a BREAK button fires the break callback with the pledge dict."""
        panel = _make_panel()
        panel.set_active_npc("lira_fence")
        panel.set_pledges(_SAMPLE_PLEDGES)
        surf, rect = _make_surface()
        panel.draw(surf, rect)

        break_cb = MagicMock()
        panel.set_break_callback(break_cb)

        if panel._break_btn_rects:
            btn_rect, pledge = panel._break_btn_rects[0]
            event = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": btn_rect.center, "button": 1},
            )
            panel.handle_event(event)
            break_cb.assert_called_once_with(pledge)

    def test_non_click_event_ignored(self) -> None:
        """Non-MOUSEBUTTONDOWN events do not invoke callbacks."""
        panel = _make_panel()
        swear_cb = MagicMock()
        panel.set_swear_callback(swear_cb)
        event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_a})
        panel.handle_event(event)
        swear_cb.assert_not_called()
