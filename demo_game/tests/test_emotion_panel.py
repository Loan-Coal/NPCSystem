"""
Module: test_emotion_panel
Layer: demo_game (tests)
Purpose: Unit tests for EmotionPanelWidget state setters and draw guard.
         No pygame display init required — Surface and Rect are mocked.
Dependencies: demo_game.ui.emotion_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    from demo_game.ui.panels.emotion_panel import EmotionPanelWidget
    return EmotionPanelWidget(_MockFont(), _MockFont())


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_label_empty() -> None:
    w = _make_widget()
    assert w._label == ""


def test_initial_valence_zero() -> None:
    w = _make_widget()
    assert w._valence == 0.0


def test_initial_arousal_zero() -> None:
    w = _make_widget()
    assert w._arousal == 0.0


# ---------------------------------------------------------------------------
# set_emotion
# ---------------------------------------------------------------------------


def test_set_emotion_stores_label() -> None:
    w = _make_widget()
    w.set_emotion("calm", 0.5, 0.3)
    assert w._label == "calm"


def test_set_emotion_stores_valence() -> None:
    w = _make_widget()
    w.set_emotion("fearful", -0.7, 0.8)
    assert w._valence == pytest.approx(-0.7)


def test_set_emotion_stores_arousal() -> None:
    w = _make_widget()
    w.set_emotion("excited", 0.6, 0.9)
    assert w._arousal == pytest.approx(0.9)


def test_set_emotion_overwrites_previous() -> None:
    w = _make_widget()
    w.set_emotion("calm", 0.2, 0.1)
    w.set_emotion("angry", -0.8, 0.95)
    assert w._label == "angry"
    assert w._valence == pytest.approx(-0.8)
    assert w._arousal == pytest.approx(0.95)


def test_set_emotion_accepts_float_strings_coerced() -> None:
    w = _make_widget()
    w.set_emotion("neutral", "0.0", "0.5")  # type: ignore[arg-type]
    assert w._valence == pytest.approx(0.0)
    assert w._arousal == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# draw — smoke test (no crash without display)
# ---------------------------------------------------------------------------


def test_draw_no_data_does_not_crash() -> None:
    with patch("demo_game.ui.panels.emotion_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.line = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface = MagicMock()
        rect = MagicMock()
        rect.x, rect.y, rect.width, rect.height = 0, 0, 200, 400
        rect.centerx, rect.centery = 100, 200
        rect.right, rect.bottom = 200, 400
        w = _make_widget()
        w.draw(surface, rect)   # should not raise


def test_draw_with_data_does_not_crash() -> None:
    with patch("demo_game.ui.panels.emotion_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.line = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface = MagicMock()
        rect = MagicMock()
        rect.x, rect.y, rect.width, rect.height = 0, 0, 300, 400
        rect.right, rect.bottom = 300, 400
        w = _make_widget()
        w.set_emotion("happy", 0.7, 0.6)
        w.draw(surface, rect)   # should not raise
