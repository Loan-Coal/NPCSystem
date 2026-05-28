"""
Module: test_widgets
Layer: demo_game (tests)
Purpose: TDD unit tests for demo_game.ui.widgets — _wrap_text and ScrollableLog
         word-wrap + pixel-scroll behaviour. No pygame display init required.
Dependencies: demo_game.ui.widgets, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.ui.widgets import ScrollableLog, _wrap_text


# ---------------------------------------------------------------------------
# Mock font: 8px per character, 16px line height — fully predictable widths.
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame.font.Font stand-in that reports 8px per character."""

    CHAR_W = 8
    LINE_H = 16

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * self.CHAR_W, self.LINE_H)

    def get_linesize(self) -> int:
        return self.LINE_H

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * self.CHAR_W
        surf.get_height.return_value = self.LINE_H
        return surf


# ---------------------------------------------------------------------------
# _wrap_text
# ---------------------------------------------------------------------------


def test_wrap_text_short_string_fits_one_line() -> None:
    font = _MockFont()
    # "hello" = 40px; max = 100px → single line
    result = _wrap_text(font, "hello", max_width=100)
    assert result == ["hello"]


def test_wrap_text_long_string_splits_at_word_boundary() -> None:
    font = _MockFont()
    # CHAR_W=8; max=40px → 5 chars per line exactly
    # "hello world foo bar" → ["hello", "world", "foo", "bar"]
    result = _wrap_text(font, "hello world foo bar", max_width=40)
    assert result == ["hello", "world", "foo", "bar"]
    # verify no line exceeds max_width
    for line in result:
        assert font.size(line)[0] <= 40


def test_wrap_text_single_word_longer_than_max_width_stays_on_one_line() -> None:
    font = _MockFont()
    # A single word that exceeds max_width must still be placed on its own line
    # (no sub-word splitting expected).
    result = _wrap_text(font, "superlongword", max_width=40)
    assert len(result) == 1
    assert result[0] == "superlongword"


def test_wrap_text_empty_string_returns_one_empty_line() -> None:
    font = _MockFont()
    result = _wrap_text(font, "", max_width=100)
    assert result == [""]


def test_wrap_text_multi_word_all_fit_on_one_line() -> None:
    font = _MockFont()
    # "ab cd" = 5 chars = 40px; max = 40px → fits as one line
    result = _wrap_text(font, "ab cd", max_width=40)
    assert result == ["ab cd"]


def test_wrap_text_preserves_all_words() -> None:
    font = _MockFont()
    text = "the quick brown fox jumps over the lazy dog"
    result = _wrap_text(font, text, max_width=80)
    assert " ".join(result) == text


# ---------------------------------------------------------------------------
# ScrollableLog — add_message / clear / scroll reset
# ---------------------------------------------------------------------------


def _make_log() -> ScrollableLog:
    return ScrollableLog(_MockFont(), _MockFont())


def test_scrollable_log_add_message_stores_entry() -> None:
    log = _make_log()
    log.add_message("Mira", "Hello traveller.", is_player=False)
    assert len(log._messages) == 1
    label, body, _ = log._messages[0]
    assert label == "Mira"
    assert body == "Hello traveller."


def test_scrollable_log_add_message_resets_scroll_to_bottom() -> None:
    log = _make_log()
    # simulate the user having scrolled up
    log._scroll_px = 200
    log.add_message("You", "Hi", is_player=True)
    assert log._scroll_px == 0


def test_scrollable_log_clear_removes_all_messages() -> None:
    log = _make_log()
    log.add_message("Mira", "Hello", is_player=False)
    log.add_message("You", "Hi", is_player=True)
    log.clear()
    assert log._messages == []


def test_scrollable_log_clear_resets_scroll_to_bottom() -> None:
    log = _make_log()
    log.add_message("Mira", "Hello")
    log._scroll_px = 150
    log.clear()
    assert log._scroll_px == 0


def test_scrollable_log_respects_max_messages() -> None:
    log = ScrollableLog(_MockFont(), _MockFont(), max_messages=3)
    for i in range(5):
        log.add_message("NPC", f"msg {i}")
    assert len(log._messages) == 3
    # oldest messages evicted — last 3 remain
    assert log._messages[-1][1] == "msg 4"


def test_scrollable_log_player_message_uses_player_colour() -> None:
    log = _make_log()
    log.add_message("You", "test", is_player=True)
    _, _, colour = log._messages[0]
    # player colour is blue-dominant (see widgets.py _CLR_PLAYER_LABEL)
    r, g, b = colour
    assert b > r


def test_scrollable_log_error_message_uses_red_colour() -> None:
    log = _make_log()
    log.add_message("ERROR", "Something went wrong", is_error=True)
    _, _, colour = log._messages[0]
    r, g, b = colour
    assert r > g and r > b


# ---------------------------------------------------------------------------
# Per-NPC log isolation (pattern verification, no GameWindow init needed)
# ---------------------------------------------------------------------------


def test_independent_logs_do_not_share_messages() -> None:
    log_a = _make_log()
    log_b = _make_log()
    log_a.add_message("Mira", "I am Mira")
    assert len(log_b._messages) == 0


def test_switching_npc_dict_preserves_history() -> None:
    logs: dict[str, ScrollableLog] = {}

    def get_log(npc_id: str) -> ScrollableLog:
        if npc_id not in logs:
            logs[npc_id] = _make_log()
        return logs[npc_id]

    get_log("mira_innkeeper").add_message("Mira", "Hello from Mira")
    get_log("captain_sorn").add_message("Sorn", "Report, soldier")

    # Switch back to Mira — history preserved
    assert len(get_log("mira_innkeeper")._messages) == 1
    assert get_log("mira_innkeeper")._messages[0][1] == "Hello from Mira"
    assert len(get_log("captain_sorn")._messages) == 1


# ---------------------------------------------------------------------------
# Tab-toggle state machine (no pygame display needed)
# ---------------------------------------------------------------------------


class _ToggleState:
    """Minimal stand-in for the _show_sidebar flag + Tab key logic in GameWindow."""

    def __init__(self) -> None:
        self.show_sidebar: bool = False

    def on_tab(self) -> None:
        self.show_sidebar = not self.show_sidebar


def test_sidebar_toggle_initial_state_is_false() -> None:
    state = _ToggleState()
    assert state.show_sidebar is False


def test_sidebar_toggle_flips_on_tab_and_back() -> None:
    state = _ToggleState()
    state.on_tab()
    assert state.show_sidebar is True
    state.on_tab()
    assert state.show_sidebar is False


def test_response_routed_to_correct_npc_log() -> None:
    logs: dict[str, ScrollableLog] = {}

    def get_log(npc_id: str) -> ScrollableLog:
        if npc_id not in logs:
            logs[npc_id] = _make_log()
        return logs[npc_id]

    active_npc = "captain_sorn"  # player is looking at Sorn

    # response arrives for mira (background — player already switched away)
    response_npc_id = "mira_innkeeper"
    get_log(response_npc_id).add_message("Mira", "Late reply from Mira")

    # Sorn's log is untouched
    assert "captain_sorn" not in logs or len(logs["captain_sorn"]._messages) == 0
    # Mira's log has the message
    assert logs["mira_innkeeper"]._messages[0][1] == "Late reply from Mira"
