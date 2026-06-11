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


def test_right_panel_enum_has_sixteen_values() -> None:
    from demo_game.ui.right_panel import RightPanel

    panels = list(RightPanel)
    assert len(panels) == 16  # EXP-220 added FACTION tab


def test_right_panel_enum_values() -> None:
    from demo_game.ui.right_panel import RightPanel

    values = {p.value for p in RightPanel}
    assert "GRAPH" in values
    assert "KNOWLEDGE" in values
    assert "PLAYER STATUS" in values
    assert "CHAIN" in values
    assert "EMOTION" in values
    assert "NEEDS" in values
    assert "GOALS" in values
    assert "MEMORY" in values


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
    n_panels = len(list(RightPanel))
    for _ in range(n_panels):
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


# ---------------------------------------------------------------------------
# start_item_pick
# ---------------------------------------------------------------------------


def test_start_item_pick_switches_to_inventory_tab() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    renderer.start_item_pick(lambda _: None)
    assert renderer.active == RightPanel.PLAYER_INVENTORY


def test_start_item_pick_on_selected_calls_callback_with_item() -> None:
    renderer = _make_renderer()
    received = []
    renderer.start_item_pick(lambda item: received.append(item))
    item = {"id": "pouch_01", "name": "Coin Pouch"}
    # simulate inventory panel firing the wrapped on_selected
    renderer._inventory_panel._on_item_selected(item)
    assert received == [item]


def test_start_item_pick_on_selected_returns_to_actions_tab() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    renderer.start_item_pick(lambda _: None)
    renderer._inventory_panel._on_item_selected({"id": "x"})
    assert renderer.active == RightPanel.ACTIONS


def test_start_item_pick_on_cancel_returns_to_actions_tab() -> None:
    from demo_game.ui.right_panel import RightPanel

    renderer = _make_renderer()
    renderer.start_item_pick(lambda _: None)
    renderer._inventory_panel._on_give_cancel()
    assert renderer.active == RightPanel.ACTIONS


def test_start_item_pick_on_selected_stops_give_mode() -> None:
    renderer = _make_renderer()
    renderer.start_item_pick(lambda _: None)
    renderer._inventory_panel._on_item_selected({"id": "x"})
    assert renderer._inventory_panel._give_mode is False


def test_start_item_pick_on_cancel_stops_give_mode() -> None:
    renderer = _make_renderer()
    renderer.start_item_pick(lambda _: None)
    renderer._inventory_panel._on_give_cancel()
    assert renderer._inventory_panel._give_mode is False


# ---------------------------------------------------------------------------
# set_travel_callback
# ---------------------------------------------------------------------------


def test_set_travel_callback_delegates_to_actions_panel() -> None:
    renderer = _make_renderer()
    called = []
    renderer.set_travel_callback(lambda: called.append(1))
    renderer._actions_panel._on_travel()
    assert called == [1]
