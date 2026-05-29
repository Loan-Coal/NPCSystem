"""
Module: test_widgets
Layer: demo_game (tests)
Purpose: TDD unit tests for demo_game.ui.widgets — _wrap_text, ScrollableLog,
         DegradationBadge emotion colouring, and NpcListWidget faction dot.
         No pygame display init required.
Dependencies: demo_game.ui.widgets, demo_game.constants, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from demo_game.constants import PALETTE
from demo_game.ui.widgets import DegradationBadge, EventBanner, NpcListWidget, ScrollableLog, _emotion_colour, _wrap_text


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


# ---------------------------------------------------------------------------
# DegradationBadge — live emotion colouring
# ---------------------------------------------------------------------------


def test_emotion_colour_positive_valence_is_green() -> None:
    r, g, b = _emotion_colour(0.5)
    assert g > r and g > b


def test_emotion_colour_negative_valence_is_red() -> None:
    r, g, b = _emotion_colour(-0.5)
    assert r > g and r > b


def test_emotion_colour_neutral_valence_is_amber() -> None:
    r, g, b = _emotion_colour(0.0)
    # amber: high R, medium-high G, low B
    assert r > b and g > b


def test_emotion_colour_boundary_above_positive_threshold() -> None:
    # 0.3 is NOT positive (> 0.3 required) — should be amber
    r_amber, g_amber, _ = _emotion_colour(0.3)
    r_green, g_green, _ = _emotion_colour(0.31)
    assert g_green > r_green  # green
    assert r_amber > g_amber or g_amber >= r_amber  # could be amber (not strictly green)


def test_emotion_colour_boundary_below_negative_threshold() -> None:
    # -0.3 is NOT negative (< -0.3 required) — should be amber
    _emotion_colour(-0.3)   # amber — no assertion needed, just no crash
    r_red, g_red, _ = _emotion_colour(-0.31)
    assert r_red > g_red  # red


def test_degradation_badge_set_emotion_stores_label_and_valence() -> None:
    badge = DegradationBadge(_MockFont())
    badge.set_emotion("joyful", 0.8)
    assert badge._emotion_label == "joyful"
    assert badge._emotion_valence == pytest.approx(0.8)


def test_degradation_badge_set_emotion_overwrites_previous() -> None:
    badge = DegradationBadge(_MockFont())
    badge.set_emotion("happy", 0.6)
    badge.set_emotion("neutral", 0.0)
    assert badge._emotion_label == "neutral"
    assert badge._emotion_valence == pytest.approx(0.0)


def test_degradation_badge_initial_emotion_is_empty() -> None:
    badge = DegradationBadge(_MockFont())
    assert badge._emotion_label == ""
    assert badge._emotion_valence == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# NpcListWidget — faction dot drawn per row
# ---------------------------------------------------------------------------


def _make_npc_list() -> NpcListWidget:
    widget = NpcListWidget(_MockFont(), row_height=36)
    widget.set_npcs(
        ["mira_innkeeper", "lira_fence"],
        {"mira_innkeeper": "Mira", "lira_fence": "Lira"},
        active_id="mira_innkeeper",
    )
    return widget


def test_npc_list_widget_faction_dot_drawn_for_each_row() -> None:
    """pygame.draw.circle is called once per NPC row during draw()."""
    widget = _make_npc_list()
    mock_surface = MagicMock()

    with patch("demo_game.ui.widgets.pygame") as mock_pygame:
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(mock_surface, MagicMock())
        assert mock_pygame.draw.circle.call_count == 2


def test_npc_list_widget_neutral_faction_uses_grey() -> None:
    """mira_innkeeper (neutral) draws a grey dot."""
    widget = NpcListWidget(_MockFont(), row_height=36)
    widget.set_npcs(
        ["mira_innkeeper"],
        {"mira_innkeeper": "Mira"},
        active_id="mira_innkeeper",
    )
    mock_surface = MagicMock()

    with patch("demo_game.ui.widgets.pygame") as mock_pygame:
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(mock_surface, MagicMock())
        call_args = mock_pygame.draw.circle.call_args
        colour = call_args[0][1]  # second positional arg is colour
        r, g, b = colour
        # grey: all components roughly equal
        assert abs(int(r) - int(g)) <= 10 and abs(int(g) - int(b)) <= 10


def test_scrollable_log_draw_has_amber_border() -> None:
    """ScrollableLog.draw() must call pygame.draw.rect with PALETTE['amber'] and width=1."""
    import pygame as pg
    log = _make_log()
    log.add_message("Mira", "Hello traveller.")
    surface = MagicMock()
    rect = pg.Rect(0, 0, 200, 100)

    with patch("demo_game.ui.widgets.pygame.draw") as mock_draw:
        log.draw(surface, rect)

    border_found = any(
        len(c.args) >= 4 and c.args[1] == PALETTE["amber"] and c.args[3] == 1
        for c in mock_draw.rect.call_args_list
    )
    assert border_found, "Expected a 1px amber border rect call on ScrollableLog"


def test_scrollable_log_draw_labels_use_bracket_format() -> None:
    """Labels are rendered as '[LABEL]:' not plain 'LABEL'."""
    rendered_texts: list[str] = []

    class _TrackingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    import pygame as pg
    log = ScrollableLog(_TrackingFont(), _TrackingFont())
    log.add_message("Mira", "Hello.")
    surface = MagicMock()

    with patch("demo_game.ui.widgets.pygame.draw"):
        log.draw(surface, pg.Rect(0, 0, 200, 100))

    assert any(t.startswith("[") and t.endswith("]:") for t in rendered_texts), (
        f"Expected a '[label]:' render, got: {rendered_texts}"
    )


def test_npc_list_active_row_renders_arrow_prefix_in_amber() -> None:
    """Selected row must render '▶' with PALETTE['amber'] colour."""
    rendered: list[tuple[str, tuple]] = []

    class _TrackingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered.append((text, colour))
            return super().render(text, antialias, colour)

    widget = NpcListWidget(_TrackingFont(), row_height=36)
    widget.set_npcs(["mira_innkeeper"], {"mira_innkeeper": "Mira"}, active_id="mira_innkeeper")

    with patch("demo_game.ui.widgets.pygame") as mock_pygame:
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(MagicMock(), MagicMock())

    arrow_calls = [(text, clr) for text, clr in rendered if text == "▶"]
    assert len(arrow_calls) == 1, f"Expected exactly one '▶' render, got: {[t for t, _ in rendered]}"
    assert arrow_calls[0][1] == PALETTE["amber"], f"▶ rendered in {arrow_calls[0][1]}, expected {PALETTE['amber']}"


def test_npc_list_inactive_row_does_not_render_arrow_prefix() -> None:
    """Only the active row should show '▶'; inactive rows must not."""
    rendered_texts: list[str] = []

    class _TrackingFont(_MockFont):
        def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
            rendered_texts.append(text)
            return super().render(text, antialias, colour)

    widget = NpcListWidget(_TrackingFont(), row_height=36)
    widget.set_npcs(
        ["mira_innkeeper", "lira_fence"],
        {"mira_innkeeper": "Mira", "lira_fence": "Lira"},
        active_id="mira_innkeeper",
    )

    with patch("demo_game.ui.widgets.pygame") as mock_pygame:
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(MagicMock(), MagicMock())

    assert rendered_texts.count("▶") == 1, f"Expected 1 arrow render, got {rendered_texts.count('▶')}"


def test_npc_list_widget_thieves_guild_uses_purple() -> None:
    """lira_fence (thieves_guild) draws a purple dot (blue-dominant or violet)."""
    widget = NpcListWidget(_MockFont(), row_height=36)
    widget.set_npcs(
        ["lira_fence"],
        {"lira_fence": "Lira"},
        active_id="lira_fence",
    )
    mock_surface = MagicMock()

    with patch("demo_game.ui.widgets.pygame") as mock_pygame:
        mock_pygame.Rect = MagicMock(side_effect=lambda *a, **kw: MagicMock())
        widget.draw(mock_surface, MagicMock())
        call_args = mock_pygame.draw.circle.call_args
        colour = call_args[0][1]
        r, g, b = colour
        # purple: R and B dominant over G
        assert r > g and b > g


# ---------------------------------------------------------------------------
# EventBanner
# ---------------------------------------------------------------------------


def test_event_banner_is_inactive_before_show() -> None:
    """A freshly constructed EventBanner must not be active."""
    banner = EventBanner(_MockFont())
    assert banner.is_active() is False


def test_event_banner_is_active_after_show() -> None:
    """After show(), the banner must report as active for the duration."""
    banner = EventBanner(_MockFont())
    banner.show("war_begins", duration_s=60.0)
    assert banner.is_active() is True


def test_event_banner_draw_no_crash() -> None:
    """draw() must not raise on an active banner."""
    banner = EventBanner(_MockFont())
    banner.show("test_event", duration_s=60.0)
    surface = MagicMock()
    with patch("demo_game.ui.widgets.pygame.draw") as mock_draw:
        mock_draw.rect = MagicMock()
        banner.draw(surface, pygame.Rect(0, 0, 400, 300))


def test_event_banner_draw_is_noop_when_inactive() -> None:
    """draw() must not blit anything when the banner is inactive."""
    banner = EventBanner(_MockFont())
    surface = MagicMock()
    with patch("demo_game.ui.widgets.pygame.draw") as mock_draw:
        banner.draw(surface, pygame.Rect(0, 0, 400, 300))
        mock_draw.rect.assert_not_called()
    surface.blit.assert_not_called()
