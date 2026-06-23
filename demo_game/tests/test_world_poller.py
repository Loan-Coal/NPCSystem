"""
Module: test_world_poller
Layer: demo_game (tests)
Purpose: Unit tests for demo_game.pollers.world_poller.WorldPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.pollers.world_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.pollers.world_poller import WorldPoller


def _make_client(
    engines: list[dict] | None = None,
    events: list[dict] | None = None,
    engine_raises: Exception | None = None,
    events_raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if engine_raises is not None:
        client.get_engine_status.side_effect = engine_raises
    else:
        client.get_engine_status.return_value = engines or []
    if events_raises is not None:
        client.get_recent_events.side_effect = events_raises
    else:
        client.get_recent_events.return_value = events or []
    return client


_SAMPLE_ENGINES = [
    {"engine_name": "gossip", "last_tick_id": 5, "last_error": None, "error_count": 0},
    {"engine_name": "event", "last_tick_id": 3, "last_error": None, "error_count": 0},
]

_SAMPLE_EVENTS = [
    {"event_id": "e1", "event_type": "northern_war_begins", "label": "War begins",
     "severity": 9, "tick_id": 3, "location_id": "guard_barracks", "src_character_id": ""},
]


class TestWorldPollerInitialState:
    def test_initial_engines_empty(self) -> None:
        """get_engines() returns [] before any poll has run."""
        poller = WorldPoller(_make_client(), interval_s=999.0)
        assert poller.get_engines() == []

    def test_initial_events_empty(self) -> None:
        """get_events() returns [] before any poll has run."""
        poller = WorldPoller(_make_client(), interval_s=999.0)
        assert poller.get_events() == []


class TestWorldPollerPollOnce:
    def test_poll_once_updates_engines(self) -> None:
        """After _poll_once(), get_engines() returns the fetched engine list."""
        poller = WorldPoller(_make_client(engines=_SAMPLE_ENGINES), interval_s=999.0)
        poller._poll_once()
        assert poller.get_engines() == _SAMPLE_ENGINES

    def test_poll_once_updates_events(self) -> None:
        """After _poll_once(), get_events() returns the fetched event list."""
        poller = WorldPoller(_make_client(events=_SAMPLE_EVENTS), interval_s=999.0)
        poller._poll_once()
        assert poller.get_events() == _SAMPLE_EVENTS

    def test_poll_calls_get_recent_events_with_limit(self) -> None:
        """WorldPoller forwards event_limit to get_recent_events."""
        client = _make_client()
        poller = WorldPoller(client, interval_s=999.0, event_limit=15)
        poller._poll_once()
        client.get_recent_events.assert_called_once_with(limit=15)

    def test_engine_error_does_not_crash(self) -> None:
        """get_engine_status raising EngineClientError is swallowed; events still update."""
        client = _make_client(
            events=_SAMPLE_EVENTS,
            engine_raises=EngineClientError("down"),
        )
        poller = WorldPoller(client, interval_s=999.0)
        poller._poll_once()
        # engines not updated; events are
        assert poller.get_engines() == []
        assert poller.get_events() == _SAMPLE_EVENTS

    def test_events_error_does_not_crash(self) -> None:
        """get_recent_events raising EngineClientError is swallowed; engines still update."""
        client = _make_client(
            engines=_SAMPLE_ENGINES,
            events_raises=EngineClientError("down"),
        )
        poller = WorldPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_engines() == _SAMPLE_ENGINES
        assert poller.get_events() == []

    def test_both_errors_leaves_state_empty(self) -> None:
        """Both endpoints failing leaves engines and events empty."""
        client = _make_client(
            engine_raises=EngineClientError("e"),
            events_raises=EngineClientError("e"),
        )
        poller = WorldPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_engines() == []
        assert poller.get_events() == []


class TestWorldPollerImmutability:
    def test_get_engines_returns_copy(self) -> None:
        """Mutating the returned engines list does not affect internal state."""
        poller = WorldPoller(_make_client(engines=_SAMPLE_ENGINES), interval_s=999.0)
        poller._poll_once()
        result = poller.get_engines()
        result.clear()
        assert len(poller.get_engines()) == len(_SAMPLE_ENGINES)

    def test_get_events_returns_copy(self) -> None:
        """Mutating the returned events list does not affect internal state."""
        poller = WorldPoller(_make_client(events=_SAMPLE_EVENTS), interval_s=999.0)
        poller._poll_once()
        result = poller.get_events()
        result.clear()
        assert len(poller.get_events()) == len(_SAMPLE_EVENTS)


class TestWorldPollerDaemonThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() creates a daemon thread that is alive."""
        poller = WorldPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
