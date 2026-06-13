"""
Module: test_scheme_board_panel
Layer: demo_game (tests)
Purpose: Unit tests for SchemeBoardPanelWidget (G2.2) — data storage + draw paths
         (no schemes, discovered, hidden). Surface/font calls are mocked.
Dependencies: demo_game.ui.scheme_board_panel, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


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


def _make_widget():
    from demo_game.ui.scheme_board_panel import SchemeBoardPanelWidget
    return SchemeBoardPanelWidget(_MockFont(), _MockFont())


_SAMPLE = [
    {
        "scheme_id": "lira__abc",
        "goal": "rob the vault",
        "status": "discovered",
        "discovered": True,
        "steps": [
            {"step_order": 1, "completed": True, "summary": "cased the vault"},
            {"step_order": 2, "completed": False, "summary": "bribe the guard"},
        ],
    },
    {
        "scheme_id": "vex__def",
        "goal": "spy on the council",
        "status": "active",
        "discovered": False,
        "steps": [],
    },
]


def _mock_rect():
    rect = MagicMock()
    rect.x = 0
    rect.y = 0
    rect.width = 300
    rect.height = 400
    rect.right = 300
    rect.bottom = 400
    rect.centerx = 150
    rect.centery = 200
    return rect


class TestData:
    def test_initial_schemes_empty(self) -> None:
        assert _make_widget()._schemes == []

    def test_set_schemes_stores(self) -> None:
        widget = _make_widget()
        widget.set_schemes(_SAMPLE)
        assert widget._schemes == _SAMPLE

    def test_set_schemes_none_clears(self) -> None:
        widget = _make_widget()
        widget.set_schemes(_SAMPLE)
        widget.set_schemes(None)
        assert widget._schemes == []


class TestDraw:
    def test_draw_no_schemes_no_crash(self) -> None:
        with patch("pygame.draw"), patch("pygame.Rect", side_effect=lambda *a: MagicMock()):
            _make_widget().draw(MagicMock(), _mock_rect())  # must not raise

    def test_draw_with_schemes_no_crash(self) -> None:
        with patch("pygame.draw"), patch("pygame.Rect", side_effect=lambda *a: MagicMock()):
            widget = _make_widget()
            widget.set_schemes(_SAMPLE)
            widget.draw(MagicMock(), _mock_rect())  # must not raise
