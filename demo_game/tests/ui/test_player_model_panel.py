"""
Module: test_player_model_panel
Layer: demo_game (tests)
Purpose: Unit tests for PlayerModelPanelWidget (G2.1) — data storage, None handling.
         No real pygame display required; surface and font calls are mocked.
Dependencies: demo_game.ui.player_model_panel, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class _MockFont:
    """Minimal pygame.font.Font stand-in."""

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)

    def get_linesize(self) -> int:
        return 16

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 8
        surf.get_height.return_value = 16
        return surf


def _make_widget():
    from demo_game.ui.panels.player_model_panel import PlayerModelPanelWidget
    return PlayerModelPanelWidget(_MockFont(), _MockFont())


_SAMPLE_MODEL = {
    "npc_id": "mira_innkeeper",
    "player_id": "player_demo",
    "perceived_trust": 72,
    "perceived_intent": "friendly",
    "last_updated_at": "2025-01-01T00:00:00Z",
}


# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------


class TestPlayerModelPanelWidgetData:
    def test_initial_model_is_none(self) -> None:
        """Widget starts with no model."""
        widget = _make_widget()
        assert widget._model is None

    def test_set_model_stores_data(self) -> None:
        """set_model() stores the model dict."""
        widget = _make_widget()
        widget.set_model(_SAMPLE_MODEL)
        assert widget._model == _SAMPLE_MODEL

    def test_set_model_none_clears(self) -> None:
        """set_model(None) clears the stored model."""
        widget = _make_widget()
        widget.set_model(_SAMPLE_MODEL)
        widget.set_model(None)
        assert widget._model is None


# ---------------------------------------------------------------------------
# Draw — no crash
# ---------------------------------------------------------------------------


class TestPlayerModelPanelWidgetDraw:
    def _make_surface_and_rect(self):
        surface = MagicMock()
        surface.subsurface = MagicMock(return_value=MagicMock())
        import pygame
        rect = pygame.Rect(0, 0, 300, 200)
        return surface, rect

    def test_draw_with_none_model_no_crash(self) -> None:
        """draw() with no model data must not raise."""
        with patch("pygame.draw"), patch("pygame.Rect", side_effect=lambda *a: MagicMock()):
            widget = _make_widget()
            surface = MagicMock()
            rect = MagicMock()
            rect.x = 0
            rect.y = 0
            rect.width = 300
            rect.height = 200
            rect.right = 300
            rect.bottom = 200
            rect.centerx = 150
            rect.centery = 100
            widget.draw(surface, rect)  # must not raise

    def test_draw_with_model_no_crash(self) -> None:
        """draw() with full model data must not raise."""
        with patch("pygame.draw"), patch("pygame.Rect", side_effect=lambda *a: MagicMock()):
            widget = _make_widget()
            widget.set_model(_SAMPLE_MODEL)
            surface = MagicMock()
            rect = MagicMock()
            rect.x = 0
            rect.y = 0
            rect.width = 300
            rect.height = 200
            rect.right = 300
            rect.bottom = 200
            rect.centerx = 150
            rect.centery = 100
            widget.draw(surface, rect)  # must not raise
