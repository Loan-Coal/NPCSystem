"""
Module: test_font_loader
Layer: demo_game (tests)
Purpose: TDD unit tests for FontLoader — cache hits, fallback, size isolation.
         No pygame display init required.
Dependencies: demo_game.ui.font_loader, unittest.mock
Used by: make test-demo
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_font() -> MagicMock:
    f = MagicMock()
    f.size.return_value = (8, 16)
    f.get_linesize.return_value = 16
    return f


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------


def test_font_loader_cache_hit_returns_same_object() -> None:
    """Two calls with the same size must return the exact same object."""
    from demo_game.ui.font_loader import FontLoader

    FontLoader._clear_cache()
    with patch("pygame.font.Font", return_value=_make_font()) as mock_font:
        a = FontLoader.get(14)
        b = FontLoader.get(14)

    assert a is b
    mock_font.assert_called_once()  # constructed only once


def test_font_loader_different_sizes_return_different_objects() -> None:
    from demo_game.ui.font_loader import FontLoader

    FontLoader._clear_cache()
    with patch("pygame.font.Font", side_effect=lambda *_a, **_kw: _make_font()):
        a = FontLoader.get(12)
        b = FontLoader.get(14)

    assert a is not b


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------


def test_font_loader_falls_back_when_ttf_missing() -> None:
    """If the TTF file doesn't exist, FontLoader must return a font (not raise)."""
    from demo_game.ui.font_loader import FontLoader

    FontLoader._clear_cache()
    original_path = FontLoader._FONT_PATH
    try:
        FontLoader._FONT_PATH = Path("/nonexistent/path/Font.ttf")
        fallback = _make_font()
        with patch("pygame.font.Font", side_effect=[FileNotFoundError, fallback]):
            result = FontLoader.get(16)
        assert result is fallback
    finally:
        FontLoader._FONT_PATH = original_path
        FontLoader._clear_cache()


def test_font_loader_fallback_uses_none_as_font_name() -> None:
    """Fallback call must pass None (pygame default) as the font name."""
    from demo_game.ui.font_loader import FontLoader

    FontLoader._clear_cache()
    original_path = FontLoader._FONT_PATH
    try:
        FontLoader._FONT_PATH = Path("/nonexistent/path/Font.ttf")
        calls: list = []

        def _side_effect(name, size):
            calls.append((name, size))
            if name != str(FontLoader._FONT_PATH):
                return _make_font()
            raise FileNotFoundError

        with patch("pygame.font.Font", side_effect=_side_effect):
            FontLoader.get(12)

        assert calls[-1][0] is None
    finally:
        FontLoader._FONT_PATH = original_path
        FontLoader._clear_cache()
