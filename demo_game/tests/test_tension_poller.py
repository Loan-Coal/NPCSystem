"""
Module: test_tension_poller
Layer: demo_game (tests)
Purpose: Unit tests for TensionPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.pollers.tension_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.pollers.tension_poller import TensionPoller


def _make_client(
    world_state: dict | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_world_state.side_effect = raises
    else:
        client.get_world_state.return_value = world_state
    return client


_SAMPLE_WS = {
    "epoch": "dusk",
    "max_event_severity": 7,
    "quest_generation_rate": 0.75,
    "active_conditions": [],
}


class TestTensionPollerInitialState:
    def test_initial_severity_zero(self) -> None:
        """get_tension() returns (0, 0.0) before any poll."""
        poller = TensionPoller(_make_client(), interval_s=999.0)
        severity, rate = poller.get_tension()
        assert severity == 0
        assert rate == 0.0


class TestTensionPollerPollOnce:
    def test_poll_once_stores_metrics(self) -> None:
        """_poll_once stores severity and rate from the client."""
        client = _make_client(world_state=_SAMPLE_WS)
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        severity, rate = poller.get_tension()
        assert severity == 7
        assert rate == pytest.approx(0.75)

    def test_poll_once_none_world_state_keeps_defaults(self) -> None:
        """_poll_once with None world state leaves defaults unchanged."""
        client = _make_client(world_state=None)
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        severity, rate = poller.get_tension()
        assert severity == 0
        assert rate == 0.0

    def test_poll_once_missing_keys_defaults(self) -> None:
        """_poll_once with missing keys defaults to 0/0.0."""
        client = _make_client(world_state={"epoch": "dawn"})
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        severity, rate = poller.get_tension()
        assert severity == 0
        assert rate == 0.0

    def test_poll_once_swallows_engine_client_error(self) -> None:
        """_poll_once does not raise on EngineClientError."""
        client = _make_client(raises=EngineClientError("boom"))
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        severity, rate = poller.get_tension()
        assert severity == 0

    def test_poll_once_swallows_generic_exception(self) -> None:
        """_poll_once does not raise on any Exception."""
        client = _make_client(raises=RuntimeError("network down"))
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        severity, rate = poller.get_tension()
        assert severity == 0

    def test_poll_once_updates_on_successive_calls(self) -> None:
        """_poll_once updates values across multiple polls."""
        ws_v1 = {**_SAMPLE_WS, "max_event_severity": 3}
        ws_v2 = {**_SAMPLE_WS, "max_event_severity": 9}
        client = _make_client(world_state=ws_v1)
        poller = TensionPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_tension()[0] == 3

        client.get_world_state.return_value = ws_v2
        poller._poll_once()
        assert poller.get_tension()[0] == 9


class TestTensionPollerThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that is alive."""
        poller = TensionPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
