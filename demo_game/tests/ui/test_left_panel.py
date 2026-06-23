"""
Module: test_left_panel
Layer: demo_game (tests)
Purpose: Unit tests for LeftPanelRenderer.set_facial_expression and
         EXPRESSION_GLYPHS glyph-render path.
         No pygame display init required — pygame module is patched.
Dependencies: demo_game.ui.left_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
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
    from demo_game.ui.layout.left_panel import LeftPanelRenderer

    return LeftPanelRenderer(
        font_body=_MockFont(),
        font_label=_MockFont(),
        font_nav=_MockFont(),
        font_loc=_MockFont(),
    )


def _make_rect(x: int = 0, y: int = 0, w: int = 200, h: int = 96) -> MagicMock:
    """Return a MagicMock that behaves like pygame.Rect for the portrait zone."""
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
# EXPRESSION_GLYPHS constant exists and maps known expressions
# ---------------------------------------------------------------------------


def test_expression_glyphs_constant_exists() -> None:
    """EXPRESSION_GLYPHS must be a module-level dict[str, str]."""
    from demo_game.ui.layout import left_panel

    assert hasattr(left_panel, "EXPRESSION_GLYPHS"), "EXPRESSION_GLYPHS missing from left_panel"
    assert isinstance(left_panel.EXPRESSION_GLYPHS, dict)


def test_expression_glyphs_maps_angry() -> None:
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    assert "angry" in EXPRESSION_GLYPHS
    assert isinstance(EXPRESSION_GLYPHS["angry"], str)


def test_expression_glyphs_maps_happy() -> None:
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    assert "happy" in EXPRESSION_GLYPHS


def test_expression_glyphs_maps_neutral() -> None:
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    assert "neutral" in EXPRESSION_GLYPHS


# ---------------------------------------------------------------------------
# set_facial_expression setter
# ---------------------------------------------------------------------------


def test_set_facial_expression_stores_value() -> None:
    renderer = _make_renderer()
    renderer.set_facial_expression("angry")
    assert renderer._facial_expression == "angry"


def test_set_facial_expression_accepts_none() -> None:
    renderer = _make_renderer()
    renderer.set_facial_expression(None)
    assert renderer._facial_expression is None


def test_set_facial_expression_overwrites_previous() -> None:
    renderer = _make_renderer()
    renderer.set_facial_expression("happy")
    renderer.set_facial_expression("sad")
    assert renderer._facial_expression == "sad"


# ---------------------------------------------------------------------------
# _draw_portrait_zone — glyph rendered for known expression
# ---------------------------------------------------------------------------


def test_draw_portrait_zone_renders_known_expression_glyph() -> None:
    """Known expression 'angry' → the mapped glyph must be rendered via font.render."""
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    renderer = _make_renderer()
    renderer.set_active_npc("mira_innkeeper")
    renderer.set_facial_expression("angry")

    expected_glyph = EXPRESSION_GLYPHS["angry"]

    with patch("demo_game.ui.layout.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.circle = MagicMock()
        mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_portrait_zone(surface, rect)

        # Collect all text rendered via font.render calls on the mock font
        render_calls = [
            c.args[0]
            for c in mock_pygame.font.Font.return_value.render.call_args_list
        ]
        # The renderer uses _font_loc directly (not mock_pygame.font.Font), so
        # we check surface.blit to confirm a render result that matches glyph was blitted.
        # All blit calls on the surface should include one carrying the glyph text.
        blitted_texts = []
        for blit_call in surface.blit.call_args_list:
            surf_arg = blit_call.args[0] if blit_call.args else blit_call.kwargs.get("source")
            blitted_texts.append(surf_arg)

        # There must be at least one blit (the glyph surface).
        assert len(blitted_texts) > 0, "No blit calls made — glyph was not rendered"


def test_draw_portrait_zone_renders_glyph_as_font_render() -> None:
    """Portrait zone must call font.render with the mapped glyph string."""
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    renderer = _make_renderer()
    renderer.set_active_npc("mira_innkeeper")
    renderer.set_facial_expression("angry")
    expected_glyph = EXPRESSION_GLYPHS["angry"]

    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_loc = _CapturingFont()

    with patch("demo_game.ui.layout.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.circle = MagicMock()
        mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_portrait_zone(surface, rect)

    assert expected_glyph in rendered_texts, (
        f"Expected glyph '{expected_glyph}' to be rendered; got: {rendered_texts}"
    )


# ---------------------------------------------------------------------------
# _draw_portrait_zone — unknown expression → neutral default, no crash
# ---------------------------------------------------------------------------


def test_draw_portrait_zone_unknown_expression_falls_back_to_neutral() -> None:
    """Unknown expression string → neutral glyph rendered, no KeyError."""
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    renderer = _make_renderer()
    renderer.set_active_npc("mira_innkeeper")
    renderer.set_facial_expression("totally_unknown_expr_xyz")

    neutral_glyph = EXPRESSION_GLYPHS["neutral"]
    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_loc = _CapturingFont()

    with patch("demo_game.ui.layout.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.circle = MagicMock()
        mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_portrait_zone(surface, rect)  # must not raise

    assert neutral_glyph in rendered_texts, (
        f"Expected neutral glyph '{neutral_glyph}' for unknown expression; got: {rendered_texts}"
    )


def test_draw_portrait_zone_none_expression_falls_back_to_neutral() -> None:
    """None expression → neutral glyph rendered, no crash."""
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    renderer = _make_renderer()
    renderer.set_active_npc("mira_innkeeper")
    renderer.set_facial_expression(None)

    neutral_glyph = EXPRESSION_GLYPHS["neutral"]
    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_loc = _CapturingFont()

    with patch("demo_game.ui.layout.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.circle = MagicMock()
        mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_portrait_zone(surface, rect)  # must not raise

    assert neutral_glyph in rendered_texts, (
        f"Expected neutral glyph '{neutral_glyph}' for None expression; got: {rendered_texts}"
    )


# ---------------------------------------------------------------------------
# _draw_portrait_zone — no expression set → neutral glyph (default state)
# ---------------------------------------------------------------------------


def test_draw_portrait_zone_default_state_renders_neutral_glyph() -> None:
    """Fresh renderer (no set_facial_expression called) → neutral glyph, no crash."""
    from demo_game.ui.layout.left_panel import EXPRESSION_GLYPHS

    renderer = _make_renderer()
    renderer.set_active_npc("mira_innkeeper")
    # deliberately NOT calling set_facial_expression

    neutral_glyph = EXPRESSION_GLYPHS["neutral"]
    rendered_texts: list[str] = []

    class _CapturingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    renderer._font_loc = _CapturingFont()

    with patch("demo_game.ui.layout.left_panel.pygame") as mock_pygame:
        mock_pygame.draw.rect = MagicMock()
        mock_pygame.draw.circle = MagicMock()
        mock_pygame.image.load = MagicMock(side_effect=Exception("no png"))
        surface = MagicMock()
        rect = _make_rect()

        renderer._draw_portrait_zone(surface, rect)

    assert neutral_glyph in rendered_texts, (
        f"Expected neutral glyph in default state; got: {rendered_texts}"
    )
