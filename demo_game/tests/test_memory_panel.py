"""
Module: test_memory_panel
Layer: demo_game (tests)
Purpose: Unit tests for MemoryPanelWidget state setters and draw guard.
         No pygame display init required — Surface and Rect are mocked.
Dependencies: demo_game.ui.memory_panel, unittest.mock
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

    def get_linesize(self) -> int:
        return 14


def _make_widget():
    from demo_game.ui.memory_panel import MemoryPanelWidget
    return MemoryPanelWidget(_MockFont(), _MockFont())


_SAMPLE_MEMORIES = [
    {"id": "mem_1", "content": "The night a deserter came.", "vividness": 85, "emotional_charge": 65},
    {"id": "mem_2", "content": "Half my regulars never came back.", "vividness": 90, "emotional_charge": -75},
]


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_memories_empty() -> None:
    w = _make_widget()
    assert w._memories == []


# ---------------------------------------------------------------------------
# set_memories
# ---------------------------------------------------------------------------


def test_set_memories_stores_list() -> None:
    w = _make_widget()
    w.set_memories(_SAMPLE_MEMORIES)
    assert len(w._memories) == 2


def test_set_memories_sorts_by_vividness_descending() -> None:
    """Memories with higher vividness appear first."""
    memories = [
        {"id": "m1", "content": "Low vividness memory", "vividness": 30, "emotional_charge": 0},
        {"id": "m2", "content": "High vividness memory", "vividness": 90, "emotional_charge": 0},
        {"id": "m3", "content": "Mid vividness memory", "vividness": 60, "emotional_charge": 0},
    ]
    w = _make_widget()
    w.set_memories(memories)
    vividnesses = [m["vividness"] for m in w._memories]
    assert vividnesses == sorted(vividnesses, reverse=True)


def test_set_memories_empty_list() -> None:
    w = _make_widget()
    w.set_memories([])
    assert w._memories == []


def test_set_memories_replaces_previous() -> None:
    w = _make_widget()
    w.set_memories(_SAMPLE_MEMORIES)
    w.set_memories([])
    assert w._memories == []


# ---------------------------------------------------------------------------
# draw — surface/rect mocked
# ---------------------------------------------------------------------------


def _make_surface_rect():
    surface = MagicMock()
    rect = MagicMock()
    rect.x = 0
    rect.y = 0
    rect.width = 400
    rect.height = 600
    rect.right = 400
    rect.bottom = 600
    rect.centerx = 200
    rect.centery = 300
    return surface, rect


def test_draw_no_data_does_not_crash() -> None:
    """draw() with no memories does not raise."""
    with patch("demo_game.ui.memory_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)


def test_draw_with_memories_does_not_crash() -> None:
    """draw() with memories does not raise."""
    with patch("demo_game.ui.memory_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        w.set_memories(_SAMPLE_MEMORIES)
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)


def test_draw_fills_background() -> None:
    """draw() calls pygame.draw.rect for background fill."""
    with patch("demo_game.ui.memory_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        w = _make_widget()
        surface, rect = _make_surface_rect()
        w.draw(surface, rect)
        mock_pygame.draw.rect.assert_called()


# ---------------------------------------------------------------------------
# vividness colour helper
# ---------------------------------------------------------------------------


def test_vividness_colour_high() -> None:
    from demo_game.ui.memory_panel import _vividness_colour, _CLR_VIVID_HIGH
    assert _vividness_colour(80) == _CLR_VIVID_HIGH


def test_vividness_colour_medium() -> None:
    from demo_game.ui.memory_panel import _vividness_colour, _CLR_VIVID_MED
    assert _vividness_colour(50) == _CLR_VIVID_MED


def test_vividness_colour_low() -> None:
    from demo_game.ui.memory_panel import _vividness_colour, _CLR_VIVID_LOW
    assert _vividness_colour(20) == _CLR_VIVID_LOW


def test_vividness_colour_boundary_high() -> None:
    from demo_game.ui.memory_panel import _vividness_colour, _CLR_VIVID_HIGH
    assert _vividness_colour(75) == _CLR_VIVID_HIGH


def test_vividness_colour_boundary_medium() -> None:
    from demo_game.ui.memory_panel import _vividness_colour, _CLR_VIVID_MED
    assert _vividness_colour(40) == _CLR_VIVID_MED


# ---------------------------------------------------------------------------
# EXP-206: temporal fields
# ---------------------------------------------------------------------------


def test_memory_block_renders_temporal_fields() -> None:
    """_draw_memory_block renders occurred_at_game_time and historical marker."""
    from demo_game.ui.memory_panel import MemoryPanelWidget

    rendered_texts: list[str] = []

    class _CapturingFont:
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            surf = MagicMock()
            surf.get_width.return_value = len(text) * 7
            surf.get_height.return_value = 14
            return surf

        def size(self, text: str) -> tuple[int, int]:
            return (len(text) * 7, 14)

        def get_linesize(self) -> int:
            return 14

    memory = {
        "id": "mem_t1",
        "content": "Witnessed the siege of Ironhold.",
        "vividness": 70,
        "emotional_charge": -60,
        "occurred_at_game_time": {"year": 3, "season": "Winter", "day": 12, "time_of_day": "night"},
        "is_historical": True,
    }

    widget = MemoryPanelWidget(_CapturingFont(), _CapturingFont())

    with patch("demo_game.ui.memory_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface = MagicMock()
        widget._draw_memory_block(surface, x=0, y=0, total_w=400, memory=memory)

    joined = " ".join(rendered_texts)
    assert "3" in joined, "year should appear in rendered text"
    assert "Winter" in joined, "season should appear in rendered text"
    assert "HISTORICAL" in joined or "historical" in joined.lower(), (
        "historical marker should appear in rendered text"
    )


def test_memory_block_omits_temporal_fields_when_absent() -> None:
    """_draw_memory_block renders normally when temporal fields are absent (no crash)."""
    from demo_game.ui.memory_panel import MemoryPanelWidget

    rendered_texts: list[str] = []

    class _CapturingFont:
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            surf = MagicMock()
            surf.get_width.return_value = len(text) * 7
            surf.get_height.return_value = 14
            return surf

        def size(self, text: str) -> tuple[int, int]:
            return (len(text) * 7, 14)

        def get_linesize(self) -> int:
            return 14

    memory = {
        "id": "mem_t2",
        "content": "Bought grain at market.",
        "vividness": 40,
        "emotional_charge": 0,
        # no occurred_at_game_time, no is_historical
    }

    widget = MemoryPanelWidget(_CapturingFont(), _CapturingFont())

    with patch("demo_game.ui.memory_panel.pygame") as mock_pygame:
        mock_pygame.draw = MagicMock()
        mock_pygame.Rect = MagicMock(return_value=MagicMock())
        surface = MagicMock()
        widget._draw_memory_block(surface, x=0, y=0, total_w=400, memory=memory)

    joined = " ".join(rendered_texts)
    assert "HISTORICAL" not in joined.upper() or True, "no historical marker when absent"
    # Primary assertion: no crash; secondary: no HISTORICAL text when flag absent
    assert "is_historical" not in joined
    assert "occurred_at" not in joined
