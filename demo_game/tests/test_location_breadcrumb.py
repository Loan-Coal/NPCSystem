"""
Module: test_location_breadcrumb
Layer: demo_game (tests)
Purpose: Unit tests for LeftPanelRenderer._draw_location_breadcrumb — PART_OF
         ancestor chain rendered as "A ▸ B ▸ C"; bare name when no parent.
Dependencies: demo_game.ui.left_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers (shared with test_left_panel pattern)
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame.font.Font stub for constructing LeftPanelRenderer."""

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 7
        surf.get_height.return_value = 14
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 7, 14)


def _make_renderer():
    """Construct a LeftPanelRenderer with mock fonts (no display needed)."""
    from demo_game.ui.left_panel import LeftPanelRenderer

    return LeftPanelRenderer(
        font_body=_MockFont(),
        font_label=_MockFont(),
        font_nav=_MockFont(),
        font_loc=_MockFont(),
    )


def _make_rect(x: int = 0, y: int = 0, w: int = 300, h: int = 80) -> MagicMock:
    """Return a MagicMock that behaves like pygame.Rect."""
    rect = MagicMock()
    rect.x = x
    rect.y = y
    rect.width = w
    rect.height = h
    rect.centerx = x + w // 2
    rect.centery = y + h // 2
    rect.right = x + w
    rect.bottom = y + h
    return rect


# ---------------------------------------------------------------------------
# build_location_breadcrumb — pure function under test
# ---------------------------------------------------------------------------


def test_location_breadcrumb_renders_chain() -> None:
    """Mock PART_OF edges (tavern → market_district → kingsport) → chain rendered."""
    from demo_game.ui.left_panel import build_location_breadcrumb

    # Simulate: tavern PART_OF market_district PART_OF kingsport (no further parent)
    def mock_get_edges(edge_type: str, src_id: str | None = None, **_kwargs) -> list[dict]:
        if edge_type != "PART_OF":
            return []
        chain = {
            "tavern": [{"src_id": "tavern", "dst_id": "market_district"}],
            "market_district": [{"src_id": "market_district", "dst_id": "kingsport"}],
            "kingsport": [],
        }
        return chain.get(src_id or "", [])

    result = build_location_breadcrumb("tavern", mock_get_edges)
    assert result == "tavern ▸ market_district ▸ kingsport"


def test_breadcrumb_bare_name_when_no_parent() -> None:
    """When no PART_OF edge exists, the breadcrumb is just the bare location name."""
    from demo_game.ui.left_panel import build_location_breadcrumb

    def mock_get_edges(edge_type: str, src_id: str | None = None, **_kwargs) -> list[dict]:
        return []

    result = build_location_breadcrumb("market_square", mock_get_edges)
    assert result == "market_square"


def test_breadcrumb_two_level_chain() -> None:
    """Single PART_OF parent → 'child ▸ parent'."""
    from demo_game.ui.left_panel import build_location_breadcrumb

    def mock_get_edges(edge_type: str, src_id: str | None = None, **_kwargs) -> list[dict]:
        if src_id == "tavern":
            return [{"src_id": "tavern", "dst_id": "kingsport"}]
        return []

    result = build_location_breadcrumb("tavern", mock_get_edges)
    assert result == "tavern ▸ kingsport"


def test_breadcrumb_cycle_guard() -> None:
    """Malformed graph with a cycle must not loop forever — terminates safely."""
    from demo_game.ui.left_panel import build_location_breadcrumb

    # tavern → a → b → tavern (cycle)
    def mock_get_edges(edge_type: str, src_id: str | None = None, **_kwargs) -> list[dict]:
        cycle = {
            "tavern": [{"src_id": "tavern", "dst_id": "a"}],
            "a": [{"src_id": "a", "dst_id": "b"}],
            "b": [{"src_id": "b", "dst_id": "tavern"}],
        }
        return cycle.get(src_id or "", [])

    # Should not raise or hang; returns some finite string.
    result = build_location_breadcrumb("tavern", mock_get_edges)
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# _draw_location_breadcrumb — renders breadcrumb string onto the panel
# ---------------------------------------------------------------------------


def test_draw_location_breadcrumb_renders_text_via_font() -> None:
    """_draw_location_breadcrumb must call font.render with the breadcrumb string."""
    renderer = _make_renderer()
    renderer._active_location_id = "tavern"

    # Patch client call inside the renderer
    breadcrumb_text = "tavern ▸ market_district"

    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_label = _CapturingFont()

    with patch("demo_game.ui.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_location_breadcrumb(surface, rect, breadcrumb_text)

    assert breadcrumb_text in rendered_texts, (
        f"Expected breadcrumb '{breadcrumb_text}' to be rendered; got: {rendered_texts}"
    )


def test_draw_location_breadcrumb_bare_name_is_noop() -> None:
    """When breadcrumb is the bare name (no separator), nothing is rendered.

    The existing location-title already shows the name; no extra blit is needed.
    """
    renderer = _make_renderer()
    renderer._active_location_id = "market_square"

    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_label = _CapturingFont()

    with patch("demo_game.ui.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_location_breadcrumb(surface, rect, "market_square")

    # No extra font.render call — no-op for bare names.
    assert "market_square" not in rendered_texts
    surface.blit.assert_not_called()
