"""
Module: test_game_window
Layer: demo_game (tests)
Purpose: Unit tests for GameWindow layout attribute computation. No pygame display
         required — pygame.display.set_mode is mocked to avoid headless failures.
Dependencies: demo_game.ui.game_window, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_game_window(window_w: int, window_h: int):
    """Construct a GameWindow with all external I/O mocked."""
    mock_client = MagicMock()
    mock_cfg = MagicMock()
    mock_cfg.DEMO_PLAYER_ID = "player_1"
    mock_cfg.NPC_BASE_URL = "http://localhost:8000"
    mock_cfg.NPC_API_KEY = "test"
    mock_cfg.NPC_DIALOGUE_TIMEOUT_S = 10
    mock_cfg.NPC_GRAPH_TIMEOUT_S = 10

    with (
        patch("pygame.init"),
        patch("pygame.display.set_mode", return_value=MagicMock()),
        patch("pygame.display.set_caption"),
        patch("demo_game.ui.font_loader.FontLoader.get", return_value=MagicMock()),
        patch("demo_game.ui.game_window.GraphPoller") as mock_gp,
        patch("demo_game.ui.game_window.WorldStatePoller") as mock_wsp,
        patch("demo_game.ui.game_window.EmotionPoller") as mock_ep,
        patch("demo_game.ui.game_window.LeftPanelRenderer") as mock_lp,
        patch("demo_game.ui.game_window.RightPanelRenderer") as mock_rp,
    ):
        mock_gp.return_value.start = MagicMock()
        mock_wsp.return_value.start = MagicMock()
        mock_ep.return_value.start = MagicMock()
        mock_ep.return_value.set_active_npc = MagicMock()
        mock_lp.return_value.setup = MagicMock()

        from demo_game.ui.game_window import GameWindow, _LEFT_PANEL_RATIO, _NAV_BAR_H
        gw = GameWindow(mock_client, mock_cfg, window_w=window_w, window_h=window_h)
        return gw, _LEFT_PANEL_RATIO, _NAV_BAR_H


class TestGameWindowLayout:
    def test_layout_1280x720(self) -> None:
        gw, ratio, nav_h = _make_game_window(1280, 720)
        expected_left_w = int(1280 * ratio)
        assert gw._left_w == expected_left_w
        assert gw._right_x == expected_left_w + 4
        assert gw._right_w == 1280 - (expected_left_w + 4)
        assert gw._usable_h == 720 - nav_h
        assert gw._right_h == 720 - nav_h

    def test_layout_1920x1080(self) -> None:
        gw, ratio, nav_h = _make_game_window(1920, 1080)
        expected_left_w = int(1920 * ratio)
        assert gw._left_w == expected_left_w
        assert gw._right_x == expected_left_w + 4
        assert gw._right_w == 1920 - (expected_left_w + 4)
        assert gw._usable_h == 1080 - nav_h
        assert gw._right_h == 1080 - nav_h

    def test_right_x_is_left_w_plus_gutter(self) -> None:
        gw, _, _ = _make_game_window(1280, 720)
        assert gw._right_x == gw._left_w + 4

    def test_right_w_fills_remaining_space(self) -> None:
        gw, _, _ = _make_game_window(1280, 720)
        assert gw._right_x + gw._right_w == 1280

    def test_usable_h_equals_right_h(self) -> None:
        gw, _, _ = _make_game_window(1280, 720)
        assert gw._usable_h == gw._right_h

    def test_larger_window_has_larger_panels(self) -> None:
        gw_small, _, _ = _make_game_window(1280, 720)
        gw_large, _, _ = _make_game_window(1920, 1080)
        assert gw_large._left_w > gw_small._left_w
        assert gw_large._right_w > gw_small._right_w
        assert gw_large._usable_h > gw_small._usable_h
