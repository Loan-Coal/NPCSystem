"""
Module: test_quest_panel
Layer: demo_game (tests)
Purpose: TDD unit tests for QuestPanelWidget — empty state and quest card rendering.
         No pygame display init required.
Dependencies: demo_game.ui.quest_panel, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Mock helpers
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


def _mock_rect(x: int = 0, y: int = 0, w: int = 400, h: int = 300) -> MagicMock:
    rect = MagicMock()
    rect.x = x
    rect.y = y
    rect.width = w
    rect.height = h
    rect.centerx = x + w // 2
    rect.centery = y + h // 2
    return rect


# ---------------------------------------------------------------------------
# QuestPanelWidget — no quest data
# ---------------------------------------------------------------------------


def test_quest_panel_no_data_draws_without_crash() -> None:
    from unittest.mock import patch
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font)
    surface = MagicMock()
    with patch("pygame.draw.rect"):
        widget.draw(surface, _mock_rect())


def test_quest_panel_defaults_to_none() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font)
    assert widget._quest_data is None


# ---------------------------------------------------------------------------
# QuestPanelWidget — with quest data
# ---------------------------------------------------------------------------


_SAMPLE_QUEST = {
    "title": "Fetch the Northern Spices",
    "description": "Aldric needs rare spices from the northern traders.",
    "status": "available",
}


def test_quest_panel_with_data_stores_quest() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font, quest_data=_SAMPLE_QUEST)
    assert widget._quest_data == _SAMPLE_QUEST


def test_quest_panel_with_data_draws_without_crash() -> None:
    from unittest.mock import patch
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font, quest_data=_SAMPLE_QUEST)
    surface = MagicMock()
    with patch("pygame.draw.rect"):
        widget.draw(surface, _mock_rect())


def test_quest_panel_set_quest_updates_data() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font)
    assert widget._quest_data is None
    widget.set_quest(_SAMPLE_QUEST)
    assert widget._quest_data == _SAMPLE_QUEST


def test_quest_panel_set_quest_to_none_clears_data() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font, quest_data=_SAMPLE_QUEST)
    widget.set_quest(None)
    assert widget._quest_data is None


# ---------------------------------------------------------------------------
# QuestPanelWidget — handle_event is a no-op
# ---------------------------------------------------------------------------


def test_quest_panel_handle_event_no_op() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font)
    widget.handle_event(MagicMock())  # must not raise


# ---------------------------------------------------------------------------
# QuestPanelWidget — set_accept_callback + set_status
# ---------------------------------------------------------------------------


def test_quest_panel_set_accept_callback_stores_callable() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    cb = MagicMock()
    font = _MockFont()
    widget = QuestPanelWidget(font, font)
    widget.set_accept_callback(cb)
    assert widget._on_accept is cb


def test_quest_panel_set_status_overrides_displayed_status() -> None:
    from demo_game.ui.quest_panel import QuestPanelWidget

    font = _MockFont()
    widget = QuestPanelWidget(font, font, quest_data=_SAMPLE_QUEST)
    widget.set_status("active")
    assert widget._status_override == "active"


def test_quest_panel_accept_button_click_fires_callback() -> None:
    """When status=='offered' and the accept button rect is clicked, callback fires."""
    import pygame
    from demo_game.ui.quest_panel import QuestPanelWidget

    cb = MagicMock()
    font = _MockFont()
    offered_quest = dict(_SAMPLE_QUEST, status="offered")
    widget = QuestPanelWidget(font, font, quest_data=offered_quest)
    widget.set_accept_callback(cb)

    # Manually set the rect as draw() would — simulate it being at (10, 200)
    widget._accept_rect = pygame.Rect(10, 200, 120, 28)

    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (70, 210)  # inside the rect
    widget.handle_event(event)
    cb.assert_called_once()


def test_quest_panel_accept_button_click_outside_does_not_fire() -> None:
    """A click outside the accept rect must not fire the callback."""
    import pygame
    from demo_game.ui.quest_panel import QuestPanelWidget

    cb = MagicMock()
    font = _MockFont()
    offered_quest = dict(_SAMPLE_QUEST, status="offered")
    widget = QuestPanelWidget(font, font, quest_data=offered_quest)
    widget.set_accept_callback(cb)
    widget._accept_rect = pygame.Rect(10, 200, 120, 28)

    event = MagicMock()
    event.type = pygame.MOUSEBUTTONDOWN
    event.button = 1
    event.pos = (500, 500)
    widget.handle_event(event)
    cb.assert_not_called()
