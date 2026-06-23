"""
Module: test_exp224_mood_contagion
Layer: demo_game (tests)
Purpose: TDD tests for EXP-224 mood-contagion visualiser slice-1.
         Covers two new capabilities:
           1. EmotionPanelWidget.set_pair_emotion() + two-NPC draw path.
           2. EmotionPoller optional second NPC (back-compat default=None).
         No pygame display required; Surface, Rect, and draw calls are mocked.
         No src/npc_engine imports.
Dependencies: demo_game.ui.emotion_panel, demo_game.emotion_poller, unittest.mock
Used by: make test-demo / pytest demo_game/tests/ -k 'emotion_panel or emotion_poller'
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockFont:
    """Minimal pygame.font.Font stand-in that avoids display initialisation."""

    def render(self, text: str, antialias: bool, colour: tuple) -> MagicMock:
        surf = MagicMock()
        surf.get_width.return_value = len(text) * 7
        surf.get_height.return_value = 14
        return surf

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 7, 14)


def _make_widget():
    """Return a fresh EmotionPanelWidget with mock fonts."""
    from demo_game.ui.panels.emotion_panel import EmotionPanelWidget
    return EmotionPanelWidget(_MockFont(), _MockFont())


def _make_client(
    primary_emotion: dict | None = None,
    pair_emotion: dict | None = None,
) -> MagicMock:
    """Return a mock EngineClient whose get_npc_emotion() is keyed by NPC id."""
    client = MagicMock()

    def _side_effect(npc_id: str) -> dict | None:
        if npc_id == "npc_a":
            return primary_emotion
        if npc_id == "npc_b":
            return pair_emotion
        return None

    client.get_npc_emotion.side_effect = _side_effect
    return client


def _make_rect(w: int = 300, h: int = 500) -> MagicMock:
    rect = MagicMock()
    rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
    rect.centerx, rect.centery = w // 2, h // 2
    rect.right, rect.bottom = w, h
    return rect


# ---------------------------------------------------------------------------
# EmotionPanelWidget — pair tests
# ---------------------------------------------------------------------------


class TestEmotionPanelRendersPair:
    """Panel must accept pair emotion data and render without crashing."""

    def test_pair_initial_state_empty(self) -> None:
        """Widget has no pair emotion set by default."""
        w = _make_widget()
        assert w._pair_label == ""
        assert w._pair_valence == 0.0
        assert w._pair_arousal == 0.0

    def test_set_pair_emotion_stores_label(self) -> None:
        """set_pair_emotion() persists label for the second NPC."""
        w = _make_widget()
        w.set_pair_emotion("npc_b", "fearful", -0.6, 0.8)
        assert w._pair_label == "fearful"

    def test_set_pair_emotion_stores_valence_and_arousal(self) -> None:
        """set_pair_emotion() persists valence and arousal for the second NPC."""
        w = _make_widget()
        w.set_pair_emotion("npc_b", "calm", 0.3, 0.2)
        assert w._pair_valence == pytest.approx(0.3)
        assert w._pair_arousal == pytest.approx(0.2)

    def test_set_pair_emotion_stores_npc_id(self) -> None:
        """set_pair_emotion() records the pair NPC id for header labelling."""
        w = _make_widget()
        w.set_pair_emotion("old_henryk", "anxious", -0.4, 0.7)
        assert w._pair_npc_id == "old_henryk"

    def test_draw_pair_does_not_crash(self) -> None:
        """draw() with both primary and pair data set must not raise."""
        with patch("demo_game.ui.panels.emotion_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.line = MagicMock()
            mock_pygame.Rect = MagicMock(return_value=MagicMock())
            surface = MagicMock()
            rect = _make_rect()
            w = _make_widget()
            w.set_emotion("happy", 0.7, 0.6)
            w.set_pair_emotion("npc_b", "sad", -0.5, 0.4)
            w.draw(surface, rect)

    def test_draw_single_no_pair_unchanged(self) -> None:
        """draw() with no pair set must still render without crashing (back-compat)."""
        with patch("demo_game.ui.panels.emotion_panel.pygame") as mock_pygame:
            mock_pygame.draw.rect = MagicMock()
            mock_pygame.draw.line = MagicMock()
            mock_pygame.Rect = MagicMock(return_value=MagicMock())
            surface = MagicMock()
            rect = _make_rect()
            w = _make_widget()
            w.set_emotion("happy", 0.7, 0.6)
            w.draw(surface, rect)  # no pair set — single render

    def test_clear_pair_emotion_resets_to_no_pair(self) -> None:
        """clear_pair_emotion() resets state so subsequent draw is single-NPC."""
        w = _make_widget()
        w.set_pair_emotion("npc_b", "sad", -0.5, 0.4)
        w.clear_pair_emotion()
        assert w._pair_label == ""
        assert w._pair_npc_id is None


# ---------------------------------------------------------------------------
# EmotionPoller — optional pair NPC tests
# ---------------------------------------------------------------------------


class TestEmotionPollerPairOptional:
    """Poller with no pair_npc_id behaves identically to the original single-NPC design."""

    def test_constructor_no_pair_back_compat(self) -> None:
        """EmotionPoller(client) with no pair_npc_id defaults to None — back-compat."""
        from demo_game.emotion_poller import EmotionPoller
        client = MagicMock()
        poller = EmotionPoller(client, interval_s=999.0)
        assert poller._pair_npc_id is None

    def test_constructor_with_pair_npc_stores_id(self) -> None:
        """EmotionPoller(client, pair_npc_id='npc_b') stores the pair id."""
        from demo_game.emotion_poller import EmotionPoller
        client = MagicMock()
        poller = EmotionPoller(client, interval_s=999.0, pair_npc_id="npc_b")
        assert poller._pair_npc_id == "npc_b"

    def test_get_pair_emotion_default_empty(self) -> None:
        """get_pair_emotion() returns ('', 0.0, 0.0) with no pair configured."""
        from demo_game.emotion_poller import EmotionPoller
        poller = EmotionPoller(MagicMock(), interval_s=999.0)
        label, valence, arousal = poller.get_pair_emotion()
        assert label == ""
        assert valence == 0.0
        assert arousal == 0.0

    def test_poll_once_primary_unchanged_with_pair_none(self) -> None:
        """Single-NPC path: primary emotion still polled correctly when pair is None."""
        from demo_game.emotion_poller import EmotionPoller
        primary_data = {"label": "calm", "valence": 0.3, "arousal": 0.2}
        client = MagicMock()
        client.get_npc_emotion.return_value = primary_data
        poller = EmotionPoller(client, interval_s=999.0)
        poller.set_active_npc("npc_a")
        poller._poll_once()
        label, valence, arousal = poller.get_emotion()
        assert label == "calm"
        assert valence == pytest.approx(0.3)
        # pair emotion still empty
        p_label, p_valence, p_arousal = poller.get_pair_emotion()
        assert p_label == ""

    def test_poll_once_fetches_pair_emotion(self) -> None:
        """When pair_npc_id is set, _poll_once() also fetches the pair's emotion."""
        from demo_game.emotion_poller import EmotionPoller
        primary_data = {"label": "happy", "valence": 0.7, "arousal": 0.5}
        pair_data = {"label": "sad", "valence": -0.6, "arousal": 0.3}

        client = _make_client(
            primary_emotion=primary_data,
            pair_emotion=pair_data,
        )
        poller = EmotionPoller(
            client, interval_s=999.0, pair_npc_id="npc_b"
        )
        poller.set_active_npc("npc_a")
        poller._poll_once()

        p_label, p_valence, p_arousal = poller.get_pair_emotion()
        assert p_label == "sad"
        assert p_valence == pytest.approx(-0.6)
        assert p_arousal == pytest.approx(0.3)

    def test_poll_once_pair_error_does_not_crash(self) -> None:
        """Pair poll failure must be swallowed; primary emotion is unaffected."""
        from demo_game.emotion_poller import EmotionPoller
        import logging
        primary_data = {"label": "happy", "valence": 0.7, "arousal": 0.5}

        client = MagicMock()

        def _side_effect(npc_id: str) -> dict:
            if npc_id == "npc_a":
                return primary_data
            raise RuntimeError("pair endpoint down")

        client.get_npc_emotion.side_effect = _side_effect
        poller = EmotionPoller(client, interval_s=999.0, pair_npc_id="npc_b")
        poller.set_active_npc("npc_a")
        poller._poll_once()  # must not raise

        label, valence, _ = poller.get_emotion()
        assert label == "happy"
        p_label, _, _ = poller.get_pair_emotion()
        assert p_label == ""  # pair data absent, not crashed

    def test_set_pair_npc_id_updates_pair(self) -> None:
        """set_pair_npc_id() changes the tracked pair and clears stale data."""
        from demo_game.emotion_poller import EmotionPoller
        poller = EmotionPoller(MagicMock(), interval_s=999.0)
        poller.set_pair_npc_id("npc_b")
        assert poller._pair_npc_id == "npc_b"
        p_label, p_valence, _ = poller.get_pair_emotion()
        assert p_label == ""
        assert p_valence == 0.0
