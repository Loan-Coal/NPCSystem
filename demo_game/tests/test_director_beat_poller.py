"""
Module: test_director_beat_poller
Layer: demo_game (tests)
Purpose: Unit tests for DirectorBeatPoller (G2.3).
         Covers: new-beat detection, pop_new_beat, degrade on error.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.director_beat_poller, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.director_beat_poller import DirectorBeatPoller

_BEAT_A = {"beat_kind": "tension_spike", "reason": "war", "npc_id": "mira_innkeeper",
            "player_id": "player_demo", "tick": 10}
_BEAT_B = {"beat_kind": "opportunity", "reason": "market", "npc_id": "aldric_merchant",
            "player_id": "player_demo", "tick": 12}


def _make_client(beats: list[dict] | None = None, raises: Exception | None = None) -> MagicMock:
    """Return a mock EngineClient with controlled director-beats behaviour."""
    client = MagicMock()
    if raises is not None:
        client.get_director_beats.side_effect = raises
    else:
        client.get_director_beats.return_value = beats if beats is not None else []
    return client


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_beats_empty_initially(self) -> None:
        """get_beats() returns [] before any poll."""
        poller = DirectorBeatPoller(_make_client(), interval_s=999.0)
        assert poller.get_beats() == []

    def test_no_new_beat_initially(self) -> None:
        """pop_new_beat() returns None before any poll."""
        poller = DirectorBeatPoller(_make_client(), interval_s=999.0)
        assert poller.pop_new_beat() is None


# ---------------------------------------------------------------------------
# _poll_once
# ---------------------------------------------------------------------------


class TestPollOnce:
    def test_stores_fetched_beats(self) -> None:
        """After _poll_once(), get_beats() returns the fetched list."""
        poller = DirectorBeatPoller(_make_client(beats=[_BEAT_A]), interval_s=999.0)
        poller._poll_once()
        assert poller.get_beats() == [_BEAT_A]

    def test_new_beat_set_on_first_non_empty_poll(self) -> None:
        """First poll with a non-empty list fires the new-beat flag."""
        poller = DirectorBeatPoller(_make_client(beats=[_BEAT_A]), interval_s=999.0)
        poller._poll_once()
        beat = poller.pop_new_beat()
        assert beat == _BEAT_A

    def test_no_new_beat_on_same_head(self) -> None:
        """No new-beat flag when same head beat is polled twice."""
        poller = DirectorBeatPoller(_make_client(beats=[_BEAT_A]), interval_s=999.0)
        poller._poll_once()
        poller.pop_new_beat()  # consume first
        poller._poll_once()
        assert poller.pop_new_beat() is None

    def test_new_beat_on_head_change(self) -> None:
        """New-beat flag fires when the head beat changes."""
        client = _make_client(beats=[_BEAT_A])
        poller = DirectorBeatPoller(client, interval_s=999.0)
        poller._poll_once()
        poller.pop_new_beat()  # consume first beat

        # Switch to a different head beat.
        client.get_director_beats.return_value = [_BEAT_B, _BEAT_A]
        poller._poll_once()
        beat = poller.pop_new_beat()
        assert beat == _BEAT_B

    def test_empty_beats_no_flag(self) -> None:
        """Empty list does not fire the new-beat flag."""
        poller = DirectorBeatPoller(_make_client(beats=[]), interval_s=999.0)
        poller._poll_once()
        assert poller.pop_new_beat() is None

    def test_error_does_not_crash(self) -> None:
        """Exceptions during polling are swallowed; beats stay empty."""
        poller = DirectorBeatPoller(
            _make_client(raises=Exception("network error")), interval_s=999.0
        )
        poller._poll_once()
        assert poller.get_beats() == []


# ---------------------------------------------------------------------------
# pop_new_beat
# ---------------------------------------------------------------------------


class TestPopNewBeat:
    def test_pop_consumes_the_cue(self) -> None:
        """pop_new_beat() returns the cue once and None on subsequent calls."""
        poller = DirectorBeatPoller(_make_client(beats=[_BEAT_A]), interval_s=999.0)
        poller._poll_once()
        first = poller.pop_new_beat()
        assert first == _BEAT_A
        second = poller.pop_new_beat()
        assert second is None

    def test_get_beats_returns_copy(self) -> None:
        """Mutating the returned list does not affect internal state."""
        poller = DirectorBeatPoller(_make_client(beats=[_BEAT_A]), interval_s=999.0)
        poller._poll_once()
        result = poller.get_beats()
        result.clear()
        assert len(poller.get_beats()) == 1


# ---------------------------------------------------------------------------
# Daemon thread
# ---------------------------------------------------------------------------


class TestDaemonThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() creates a daemon thread."""
        poller = DirectorBeatPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
