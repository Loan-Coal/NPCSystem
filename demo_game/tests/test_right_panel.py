"""
Module: test_right_panel
Layer: demo_game (tests)
Purpose: TDD unit tests for RightPanel enum and RightPanelRenderer tab-cycling logic.
         No pygame display init required — dependencies are mocked.
Dependencies: demo_game.ui.right_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_renderer():
    """Build a RightPanelRenderer with mocked graph poller and mock fonts."""
    from demo_game.ui.right_panel import RightPanelRenderer

    mock_graph_poller = MagicMock()
    font = _MockFont()
    return RightPanelRenderer(mock_graph_poller, font, font, font)


# ---------------------------------------------------------------------------
# RightPanel enum
# ---------------------------------------------------------------------------


def test_right_panel_enum_has_four_values() -> None:
    from demo_game.ui.right_panel import RightPanel

    panels = list(RightPanel)
    assert len(panels) == 4


def test_right_panel_enum_values() -> None:
    from demo_game.ui.right_panel import RightPanel

    values = {p.value for p in RightPanel}
    assert "GRAPH" in values
    assert "KNOWLEDGE" in values
    assert "PLAYER STATUS" in values
    assert "CHAIN" in values


def test_right_panel_graph_is_first() -> None:
    from demo_game.ui.right_panel import RightPanel

    assert list(RightPanel)[0] == RightPanel.GRAPH


# ---------------------------------------------------------------------------
# RightPanelRenderer — initial state
# ---------------------------------------------------------------------------


def test_renderer_initial_tab_is_graph() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    assert renderer.active == RightPanel.GRAPH


def test_renderer_show_sidebar_false_on_graph() -> None:
    renderer = _make_renderer()
    assert renderer.show_sidebar is False


# ---------------------------------------------------------------------------
# cycle_tab
# ---------------------------------------------------------------------------


def test_cycle_tab_graph_to_knowledge() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    renderer.cycle_tab()
    assert renderer.active == RightPanel.KNOWLEDGE


def test_cycle_tab_knowledge_to_player_status() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    renderer.cycle_tab()
    renderer.cycle_tab()
    assert renderer.active == RightPanel.PLAYER_STATUS


def test_cycle_tab_player_status_to_chain() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    for _ in range(3):
        renderer.cycle_tab()
    assert renderer.active == RightPanel.CHAIN


def test_cycle_tab_wraps_back_to_graph() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    for _ in range(4):
        renderer.cycle_tab()
    assert renderer.active == RightPanel.GRAPH


# ---------------------------------------------------------------------------
# show_sidebar property
# ---------------------------------------------------------------------------


def test_show_sidebar_true_only_on_knowledge() -> None:
    renderer = _make_renderer()
    assert renderer.show_sidebar is False           # GRAPH
    renderer.cycle_tab()
    assert renderer.show_sidebar is True            # KNOWLEDGE
    renderer.cycle_tab()
    assert renderer.show_sidebar is False           # PLAYER_STATUS
    renderer.cycle_tab()
    assert renderer.show_sidebar is False           # CHAIN
    renderer.cycle_tab()
    assert renderer.show_sidebar is False           # back to GRAPH
