"""
Module: test_politics_panel
Layer: demo_game (tests)
Purpose: Unit tests for PoliticsPanelWidget state setters and draw guard.
         No pygame display init required — Surface and Rect are mocked.
Dependencies: demo_game.ui.politics_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest


class _MockFont:
    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 7
        surf.get_height.return_value = 14
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 7, 14)


def _make_widget():
    from demo_game.ui.panels.politics_panel import PoliticsPanelWidget
    return PoliticsPanelWidget(_MockFont(), _MockFont())


def _make_rect(x: int = 0, y: int = 0, w: int = 300, h: int = 500) -> MagicMock:
    r = MagicMock()
    r.x, r.y, r.width, r.height = x, y, w, h
    r.right = x + w
    r.bottom = y + h
    r.centerx = x + w // 2
    r.centery = y + h // 2
    return r


_PLEDGES = [
    {"pledgee_id": "thieves_guild", "pledge_type": "fealty"},
]
_LEVERAGE = [
    {"id": "lv_1", "demand": "Keep silent or else.", "status": "held", "created_at_tick": 0},
]


class TestPoliticsPanelInitialState:
    def test_initial_pledges_empty(self) -> None:
        """Internal pledges list starts empty."""
        w = _make_widget()
        assert w._pledges == []

    def test_initial_leverage_empty(self) -> None:
        """Internal leverage list starts empty."""
        w = _make_widget()
        assert w._leverage == []


class TestPoliticsPanelSetPolitics:
    def test_set_politics_stores_pledges(self) -> None:
        """set_politics stores the pledges list."""
        w = _make_widget()
        w.set_politics(_PLEDGES, [])
        assert w._pledges == _PLEDGES

    def test_set_politics_stores_leverage(self) -> None:
        """set_politics stores the leverage list."""
        w = _make_widget()
        w.set_politics([], _LEVERAGE)
        assert w._leverage == _LEVERAGE

    def test_set_politics_stores_copy(self) -> None:
        """set_politics stores a copy — mutating the input does not change internal state."""
        w = _make_widget()
        pledges = list(_PLEDGES)
        w.set_politics(pledges, [])
        pledges.append({"extra": True})
        assert w._pledges == _PLEDGES

    def test_set_politics_replaces_previous(self) -> None:
        """Calling set_politics twice replaces the old data."""
        w = _make_widget()
        w.set_politics(_PLEDGES, _LEVERAGE)
        w.set_politics([], [])
        assert w._pledges == []
        assert w._leverage == []


def _make_rect_mock() -> MagicMock:
    r = MagicMock()
    r.x, r.y, r.width, r.height = 0, 0, 300, 500
    r.right, r.bottom = 300, 500
    r.centerx, r.centery = 150, 250
    return r


class TestPoliticsPanelDraw:
    def _draw_with_patch(self, w, pledges=None, leverage=None) -> MagicMock:
        from unittest.mock import patch
        with patch("demo_game.ui.panels.politics_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.line = MagicMock()
            mock_pygame.Rect = MagicMock(return_value=MagicMock())
            surface = MagicMock()
            rect = _make_rect_mock()
            if pledges is not None or leverage is not None:
                w.set_politics(pledges or [], leverage or [])
            w.draw(surface, rect)
            return surface

    def test_draw_does_not_raise_empty(self) -> None:
        """draw() runs without raising when both pledges and leverage are empty."""
        w = _make_widget()
        self._draw_with_patch(w)

    def test_draw_does_not_raise_with_data(self) -> None:
        """draw() runs without raising when data is populated."""
        w = _make_widget()
        self._draw_with_patch(w, _PLEDGES, _LEVERAGE)

    def test_draw_calls_blit(self) -> None:
        """draw() calls surface.blit at least once to render content."""
        w = _make_widget()
        surface = self._draw_with_patch(w, _PLEDGES, _LEVERAGE)
        assert surface.blit.call_count > 0

    def test_draw_no_data_renders_without_crash(self) -> None:
        """draw() with empty pledges and leverage does not raise."""
        w = _make_widget()
        self._draw_with_patch(w, [], [])

    def test_leverage_status_colour_held(self) -> None:
        """held status maps to amber colour."""
        from demo_game.ui.panels.politics_panel import _leverage_status_colour, _CLR_HELD
        assert _leverage_status_colour("held") == _CLR_HELD

    def test_leverage_status_colour_used(self) -> None:
        """used status maps to grey colour."""
        from demo_game.ui.panels.politics_panel import _leverage_status_colour, _CLR_USED
        assert _leverage_status_colour("used") == _CLR_USED

    def test_leverage_status_colour_exposed(self) -> None:
        """exposed status maps to red colour."""
        from demo_game.ui.panels.politics_panel import _leverage_status_colour, _CLR_EXPOSED
        assert _leverage_status_colour("exposed") == _CLR_EXPOSED

    def test_leverage_status_colour_unknown(self) -> None:
        """unknown status defaults to held colour."""
        from demo_game.ui.panels.politics_panel import _leverage_status_colour, _CLR_HELD
        assert _leverage_status_colour("mystery") == _CLR_HELD
