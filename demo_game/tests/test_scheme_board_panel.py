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


# ---------------------------------------------------------------------------
# Tracking font to assert render content
# ---------------------------------------------------------------------------


class _TrackingFont(_MockFont):
    """Records every text passed to render() for behavioral assertions."""

    def __init__(self) -> None:
        self.rendered_texts: list[str] = []

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        self.rendered_texts.append(text)
        return super().render(text, antialias, colour)


def _make_tracking_widget() -> tuple:
    from demo_game.ui.scheme_board_panel import SchemeBoardPanelWidget

    font_body = _TrackingFont()
    font_label = _TrackingFont()
    return SchemeBoardPanelWidget(font_body, font_label), font_body, font_label


class TestDrawBehavioral:
    """Behavioral assertions — verify the correct content is rendered."""

    def _draw(self, widget) -> None:
        with patch("pygame.draw"), patch("pygame.Rect", side_effect=lambda *a: MagicMock()):
            widget.draw(MagicMock(), _mock_rect())

    def test_header_always_rendered(self) -> None:
        """The INTRIGUE section header is always present regardless of scheme data."""
        widget, font_body, _ = _make_tracking_widget()
        self._draw(widget)
        assert "INTRIGUE" in font_body.rendered_texts

    def test_no_data_message_rendered_when_empty(self) -> None:
        """'No schemes known' placeholder renders when there are no schemes."""
        widget, _, font_label = _make_tracking_widget()
        self._draw(widget)
        assert "No schemes known" in font_label.rendered_texts

    def test_no_data_message_absent_when_schemes_present(self) -> None:
        """'No schemes known' placeholder is NOT rendered when schemes exist."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert "No schemes known" not in font_label.rendered_texts

    def test_discovered_badge_rendered_for_discovered_scheme(self) -> None:
        """[DISCOVERED] badge is rendered for a scheme with discovered=True."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert "[DISCOVERED]" in font_label.rendered_texts

    def test_hidden_badge_rendered_for_undiscovered_scheme(self) -> None:
        """[HIDDEN] badge is rendered for a scheme with discovered=False."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert "[HIDDEN]" in font_label.rendered_texts

    def test_scheme_goals_rendered(self) -> None:
        """Both scheme goal strings appear in body-font render calls."""
        widget, font_body, _ = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert "rob the vault" in font_body.rendered_texts
        assert "spy on the council" in font_body.rendered_texts

    def test_step_summaries_rendered(self) -> None:
        """Step summaries from the discovered scheme appear in label-font render calls."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        # Both steps of the first (discovered) scheme have summaries.
        assert any("cased the vault" in t for t in font_label.rendered_texts)
        assert any("bribe the guard" in t for t in font_label.rendered_texts)

    def test_completed_step_uses_checkmark_marker(self) -> None:
        """Completed steps use the ✓ marker."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert any(t.startswith("✓") for t in font_label.rendered_texts)

    def test_pending_step_uses_bullet_marker(self) -> None:
        """Pending (not completed) steps use the • marker."""
        widget, _, font_label = _make_tracking_widget()
        widget.set_schemes(_SAMPLE)
        self._draw(widget)
        assert any(t.startswith("•") for t in font_label.rendered_texts)
