"""
Module: test_inspect_panel
Layer: demo_game (tests)
Purpose: TDD unit tests for InspectPanelWidget data handling and row building.
         No pygame display init required — surfaces are mocked.
Dependencies: demo_game.ui.inspect_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

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


def _make_widget():
    from demo_game.ui.panels.inspect_panel import InspectPanelWidget

    return InspectPanelWidget(_MockFont(), _MockFont())


def _make_surface(w: int = 300, h: int = 600) -> MagicMock:
    surf = MagicMock()
    sub = MagicMock()
    sub.fill = MagicMock()
    surf.subsurface.return_value = sub
    return surf


def _make_rect(x: int = 0, y: int = 0, w: int = 300, h: int = 600):
    import pygame

    return pygame.Rect(x, y, w, h)


# ---------------------------------------------------------------------------
# InspectPanelWidget — initial state
# ---------------------------------------------------------------------------


def test_widget_starts_empty() -> None:
    w = _make_widget()
    assert w._npc_id == ""
    assert w._data == {}


def test_set_data_stores_npc_id() -> None:
    w = _make_widget()
    w.set_data("captain_sorn", {"character": {"name": "Captain Sorn"}})
    assert w._npc_id == "captain_sorn"


def test_set_data_resets_scroll() -> None:
    w = _make_widget()
    w._scroll_y = 200
    w.set_data("npc", {})
    assert w._scroll_y == 0


def test_clear_resets_all() -> None:
    w = _make_widget()
    w.set_data("captain_sorn", {"character": {"name": "Captain Sorn"}})
    w.clear()
    assert w._npc_id == ""
    assert w._data == {}
    assert w._scroll_y == 0


# ---------------------------------------------------------------------------
# InspectPanelWidget — row builder
# ---------------------------------------------------------------------------


def test_build_rows_includes_character_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {"character": {"archetype": "guard", "currency_balance": 50}})
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "CHARACTER" in section_labels


def test_build_rows_archetype_field() -> None:
    w = _make_widget()
    w.set_data("npc1", {"character": {"archetype": "merchant"}})
    rows = w._build_rows()
    field_values = {r[1]: r[2] for r in rows if r[0] == "field"}
    assert field_values.get("Archetype") == "merchant"


def test_build_rows_no_factions_section_when_empty() -> None:
    w = _make_widget()
    w.set_data("npc1", {"character": {}, "factions": []})
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "FACTION STANDINGS" not in section_labels


def test_build_rows_faction_section_present_when_data_exists() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "factions": [{"faction_id": "guards_guild", "standing": 75}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "FACTION STANDINGS" in section_labels


def test_build_rows_faction_item_text() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "factions": [{"faction_id": "guards_guild", "standing": 75}],
    })
    rows = w._build_rows()
    item_values = [r[2] for r in rows if r[0] == "item"]
    assert any("guards_guild" in v and "standing=75" in v for v in item_values)


def test_build_rows_items_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "items": [{"name": "Northern Spice Bundle", "type": "spice", "value": 45}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "ITEMS" in section_labels


def test_build_rows_known_events_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "events": [{"id": "northern_war_begins"}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "KNOWN EVENTS" in section_labels


def test_build_rows_goals_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "goals": [{"description": "Sell all spice", "urgency": 80}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "GOALS" in section_labels


def test_build_rows_beliefs_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "beliefs": [{"content": "The war is coming", "confidence": 90}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "BELIEFS" in section_labels


def test_build_rows_graph_edges_section() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "relations": [{"type": "MEMBER_OF", "target_id": "thieves_guild"}],
    })
    rows = w._build_rows()
    section_labels = [r[1] for r in rows if r[0] == "section"]
    assert "GRAPH EDGES" in section_labels


def test_build_rows_graph_edge_item_text() -> None:
    w = _make_widget()
    w.set_data("npc1", {
        "character": {},
        "relations": [{"type": "MEMBER_OF", "target_id": "thieves_guild"}],
    })
    rows = w._build_rows()
    item_values = [r[2] for r in rows if r[0] == "item"]
    assert any("MEMBER_OF" in v and "thieves_guild" in v for v in item_values)


# ---------------------------------------------------------------------------
# InspectPanelWidget — emotion label
# ---------------------------------------------------------------------------


def test_emotion_label_with_data() -> None:
    w = _make_widget()
    w.set_data("npc1", {"character": {}, "emotion": {"label": "fearful", "valence": -0.7}})
    label = w._emotion_label()
    assert "fearful" in label
    assert "-0.7" in label


def test_emotion_label_empty() -> None:
    w = _make_widget()
    w.set_data("npc1", {"character": {}})
    assert w._emotion_label() == "—"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_join_list() -> None:
    from demo_game.ui.panels.inspect_panel import _join

    assert _join(["brave", "loyal"]) == "brave, loyal"


def test_join_empty_list() -> None:
    from demo_game.ui.panels.inspect_panel import _join

    assert _join([]) == "—"


def test_join_none() -> None:
    from demo_game.ui.panels.inspect_panel import _join

    assert _join(None) == "—"


def test_truncate_short() -> None:
    from demo_game.ui.panels.inspect_panel import _truncate

    assert _truncate("hello", 10) == "hello"


def test_truncate_long() -> None:
    from demo_game.ui.panels.inspect_panel import _truncate

    result = _truncate("a" * 20, 10)
    assert len(result) == 10
    assert result.endswith("…")
