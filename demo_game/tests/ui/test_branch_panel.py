"""
Module: test_branch_panel
Layer: demo_game (tests)
Purpose: Unit tests for BranchPanelWidget — keyboard navigation, option selection,
         cancel, and _wrap_text helper. No pygame display init required; pygame
         events are constructed as MagicMock objects following the pattern in
         test_action_bar.py.
Dependencies: demo_game.ui.branch_panel, demo_game.branches.branch_node,
              demo_game.branches.branch_effects, unittest.mock, pytest
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from demo_game.branches.branch_effects import RepDeltaEffect
from demo_game.branches.branch_node import BranchNode, BranchOption
from demo_game.ui.panels.branch_panel import (
    BranchPanelWidget,
    _handle_event,
    _wrap_text,
    _SENTINEL_CANCEL,
    _SENTINEL_QUIT,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame.font.Font stub sufficient for branch_panel rendering."""

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_height.return_value = 16
        surf.get_width.return_value = len(text) * 8
        surf.get_rect.return_value = pygame.Rect(0, 0, len(text) * 8, 16)
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)


def _make_branch() -> BranchNode:
    """Build a minimal 2-option BranchNode for tests."""
    effect_spare = RepDeltaEffect("garrick_deserter", "thieves_guild", 15, "loc_tavern", 1)
    effect_turn = RepDeltaEffect("garrick_deserter", "city_guard", 20, "loc_tavern", 1)
    opt_spare = BranchOption(label="Spare the deserter", effects=(effect_spare,))
    opt_turn = BranchOption(label="Turn him in", effects=(effect_turn,))
    return BranchNode(
        branch_id="branch_garrick_deserter",
        prompt_text="What do you do with Garrick?",
        options=(opt_spare, opt_turn),
    )


def _keydown(key: int) -> MagicMock:
    """Create a mock KEYDOWN event for the given key constant."""
    event = MagicMock()
    event.type = pygame.KEYDOWN
    event.key = key
    return event


def _other_event() -> MagicMock:
    """Create a mock event that is NOT KEYDOWN."""
    event = MagicMock()
    event.type = pygame.MOUSEMOTION
    return event


# ---------------------------------------------------------------------------
# _wrap_text
# ---------------------------------------------------------------------------


def test_wrap_text_short_string_no_wrap() -> None:
    """Short text that fits on one line is returned as a single-element list."""
    lines = _wrap_text("Hello world", max_chars=20)
    assert lines == ["Hello world"]


def test_wrap_text_long_string_wraps_at_word_boundary() -> None:
    """Long text wraps at word boundaries without splitting words."""
    text = "The quick brown fox jumps over the lazy dog"
    lines = _wrap_text(text, max_chars=20)
    for line in lines:
        assert len(line) <= 20
    assert " ".join(lines) == text


def test_wrap_text_empty_string() -> None:
    """Empty string returns a single empty-string element (no crash)."""
    lines = _wrap_text("", max_chars=20)
    assert isinstance(lines, list)
    assert len(lines) >= 1


# ---------------------------------------------------------------------------
# _handle_event — navigation
# ---------------------------------------------------------------------------


def test_handle_event_non_keydown_returns_unchanged_index() -> None:
    """Non-KEYDOWN events return the unchanged selected_index."""
    event = _other_event()
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result == (0, None)


def test_handle_event_arrow_down_wraps() -> None:
    """K_DOWN at last option wraps to index 0."""
    event = _keydown(pygame.K_DOWN)
    result = _handle_event(event, selected_index=1, n_options=2, allow_cancel=True)
    assert result == (0, None)


def test_handle_event_arrow_up_wraps() -> None:
    """K_UP at index 0 wraps to last option."""
    event = _keydown(pygame.K_UP)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result == (1, None)


def test_handle_event_arrow_down_advances() -> None:
    """K_DOWN from index 0 moves to index 1."""
    event = _keydown(pygame.K_DOWN)
    result = _handle_event(event, selected_index=0, n_options=3, allow_cancel=True)
    assert result == (1, None)


# ---------------------------------------------------------------------------
# _handle_event — confirmation
# ---------------------------------------------------------------------------


def test_handle_event_enter_confirms_current_selection() -> None:
    """K_RETURN confirms the currently selected option."""
    event = _keydown(pygame.K_RETURN)
    result = _handle_event(event, selected_index=1, n_options=2, allow_cancel=True)
    assert result == (1, 1)


def test_handle_event_digit_1_confirms_index_0() -> None:
    """Pressing '1' selects and confirms option at index 0."""
    event = _keydown(pygame.K_1)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result == (0, 0)


def test_handle_event_digit_2_confirms_index_1() -> None:
    """Pressing '2' selects and confirms option at index 1."""
    event = _keydown(pygame.K_2)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result == (1, 1)


def test_handle_event_digit_out_of_range_ignored() -> None:
    """Pressing a digit greater than n_options returns unchanged state."""
    event = _keydown(pygame.K_3)  # only 2 options
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result == (0, None)


# ---------------------------------------------------------------------------
# _handle_event — cancel / quit
# ---------------------------------------------------------------------------


def test_handle_event_escape_returns_cancel_sentinel() -> None:
    """K_ESCAPE returns _SENTINEL_CANCEL when allow_cancel=True."""
    event = _keydown(pygame.K_ESCAPE)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result is _SENTINEL_CANCEL


def test_handle_event_escape_ignored_when_cancel_disabled() -> None:
    """K_ESCAPE is ignored (no-op) when allow_cancel=False."""
    event = _keydown(pygame.K_ESCAPE)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=False)
    assert result == (0, None)


def test_handle_event_q_returns_quit_sentinel() -> None:
    """K_q returns _SENTINEL_QUIT."""
    event = _keydown(pygame.K_q)
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result is _SENTINEL_QUIT


def test_handle_event_quit_event_returns_quit_sentinel() -> None:
    """pygame.QUIT event type returns _SENTINEL_QUIT."""
    event = MagicMock()
    event.type = pygame.QUIT
    result = _handle_event(event, selected_index=0, n_options=2, allow_cancel=True)
    assert result is _SENTINEL_QUIT


# ---------------------------------------------------------------------------
# BranchPanelWidget.show — integration with mocked pygame loop
# ---------------------------------------------------------------------------


def test_show_returns_chosen_index_on_enter(monkeypatch: pytest.MonkeyPatch) -> None:
    """show() returns the highlighted index when Enter is pressed."""
    font = _MockFont()
    widget = BranchPanelWidget(
        title_font=font,
        prompt_font=font,
        option_font=font,
        hint_font=font,
    )
    branch = _make_branch()

    # Simulate: one DOWN key (moves to index 1) then ENTER.
    events = [
        _keydown(pygame.K_DOWN),
        _keydown(pygame.K_RETURN),
    ]
    event_iter = iter(events)

    def fake_get() -> list:
        try:
            return [next(event_iter)]
        except StopIteration:
            return []

    mock_surface = MagicMock()
    mock_surface.get_size.return_value = (1280, 720)

    monkeypatch.setattr("pygame.event.get", fake_get)
    monkeypatch.setattr("pygame.display.flip", lambda: None)
    monkeypatch.setattr("pygame.draw.rect", lambda *a, **kw: None)
    monkeypatch.setattr("pygame.Surface", lambda *a, **kw: MagicMock())

    result = widget.show(mock_surface, branch)
    assert result == 1


def test_show_returns_none_on_escape(monkeypatch: pytest.MonkeyPatch) -> None:
    """show() returns None when Escape is pressed and allow_cancel=True."""
    font = _MockFont()
    widget = BranchPanelWidget(
        title_font=font,
        prompt_font=font,
        option_font=font,
        hint_font=font,
    )
    branch = _make_branch()

    events = [_keydown(pygame.K_ESCAPE)]
    event_iter = iter(events)

    def fake_get() -> list:
        try:
            return [next(event_iter)]
        except StopIteration:
            return []

    mock_surface = MagicMock()
    mock_surface.get_size.return_value = (1280, 720)

    monkeypatch.setattr("pygame.event.get", fake_get)
    monkeypatch.setattr("pygame.display.flip", lambda: None)
    monkeypatch.setattr("pygame.draw.rect", lambda *a, **kw: None)
    monkeypatch.setattr("pygame.Surface", lambda *a, **kw: MagicMock())

    result = widget.show(mock_surface, branch, allow_cancel=True)
    assert result is None


def test_show_digit_key_selects_option(monkeypatch: pytest.MonkeyPatch) -> None:
    """show() returns 0 when '1' key is pressed (first option shortcut)."""
    font = _MockFont()
    widget = BranchPanelWidget(
        title_font=font,
        prompt_font=font,
        option_font=font,
        hint_font=font,
    )
    branch = _make_branch()

    events = [_keydown(pygame.K_1)]
    event_iter = iter(events)

    def fake_get() -> list:
        try:
            return [next(event_iter)]
        except StopIteration:
            return []

    mock_surface = MagicMock()
    mock_surface.get_size.return_value = (1280, 720)

    monkeypatch.setattr("pygame.event.get", fake_get)
    monkeypatch.setattr("pygame.display.flip", lambda: None)
    monkeypatch.setattr("pygame.draw.rect", lambda *a, **kw: None)
    monkeypatch.setattr("pygame.Surface", lambda *a, **kw: MagicMock())

    result = widget.show(mock_surface, branch)
    assert result == 0
