"""
Module: test_world_state_poller
Layer: demo_game (tests)
Purpose: TDD unit tests for demo_game.world_state_poller.WorldStatePoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.world_state_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.world_state_poller import WorldStatePoller


def _make_client(world_state: dict | None = None, raises: Exception | None = None) -> MagicMock:
    """Return a mock EngineClient whose get_world_state() returns world_state or raises."""
    client = MagicMock()
    if raises is not None:
        client.get_world_state.side_effect = raises
    else:
        client.get_world_state.return_value = world_state
    return client


class TestWorldStatePollerInitialState:
    def test_initial_state_empty(self) -> None:
        """get_state() returns ('', []) before any poll has run."""
        poller = WorldStatePoller(_make_client(), interval_s=999.0)
        epoch, conditions = poller.get_state()
        assert epoch == ""
        assert conditions == []


class TestWorldStatePollerPollOnce:
    def test_poll_once_updates_epoch_and_conditions(self) -> None:
        """After _poll_once() with a war world state, get_state() reflects the update."""
        ws = {"epoch": "war", "active_conditions": ["northern_war_active"]}
        poller = WorldStatePoller(_make_client(ws), interval_s=999.0)
        poller._poll_once()
        epoch, conditions = poller.get_state()
        assert epoch == "war"
        assert conditions == ["northern_war_active"]

    def test_poll_once_handles_none_response(self) -> None:
        """Client returns None (world not yet seeded) — state stays empty, no crash."""
        poller = WorldStatePoller(_make_client(None), interval_s=999.0)
        poller._poll_once()
        epoch, conditions = poller.get_state()
        assert epoch == ""
        assert conditions == []

    def test_poll_once_handles_engine_client_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Client raises EngineClientError — state unchanged, error logged as WARNING."""
        import logging
        poller = WorldStatePoller(
            _make_client(raises=EngineClientError("boom")), interval_s=999.0
        )
        with caplog.at_level(logging.WARNING, logger="demo_game.world_state_poller"):
            poller._poll_once()
        assert any("error" in r.message for r in caplog.records)
        epoch, conditions = poller.get_state()
        assert epoch == ""
        assert conditions == []

    def test_poll_once_handles_generic_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Any unexpected exception in _poll_once() is swallowed and logged as WARNING."""
        import logging
        poller = WorldStatePoller(
            _make_client(raises=RuntimeError("network down")), interval_s=999.0
        )
        with caplog.at_level(logging.WARNING, logger="demo_game.world_state_poller"):
            poller._poll_once()
        assert any("error" in r.message for r in caplog.records)


class TestWorldStatePollerImmutability:
    def test_get_state_returns_copy_of_conditions(self) -> None:
        """Mutating the returned conditions list does not affect internal state."""
        ws = {"epoch": "war", "active_conditions": ["northern_war_active"]}
        poller = WorldStatePoller(_make_client(ws), interval_s=999.0)
        poller._poll_once()

        _, conditions = poller.get_state()
        conditions.append("injected")

        _, conditions_again = poller.get_state()
        assert conditions_again == ["northern_war_active"]


class TestWorldStatePollerNewConditions:
    def test_pop_new_conditions_empty_before_any_poll(self) -> None:
        """No conditions queued before any poll has run."""
        poller = WorldStatePoller(_make_client(), interval_s=999.0)
        assert poller.pop_new_conditions() == []

    def test_pop_new_conditions_empty_after_first_poll(self) -> None:
        """First poll establishes the baseline — nothing is returned as 'new'."""
        ws = {"epoch": "war", "active_conditions": ["northern_war_active"]}
        poller = WorldStatePoller(_make_client(ws), interval_s=999.0)
        poller._poll_once()
        assert poller.pop_new_conditions() == []

    def test_pop_new_conditions_returns_diff_after_second_poll(self) -> None:
        """A condition added between polls appears on the second poll."""
        client = MagicMock()
        client.get_world_state.side_effect = [
            {"epoch": "peace", "active_conditions": []},
            {"epoch": "war",   "active_conditions": ["northern_war_active"]},
        ]
        poller = WorldStatePoller(client, interval_s=999.0)
        poller._poll_once()   # first poll — baseline
        assert poller.pop_new_conditions() == []
        poller._poll_once()   # second poll — war starts
        assert poller.pop_new_conditions() == ["northern_war_active"]

    def test_pop_new_conditions_clears_after_call(self) -> None:
        """Calling pop_new_conditions() twice returns empty list on the second call."""
        client = MagicMock()
        client.get_world_state.side_effect = [
            {"epoch": "peace", "active_conditions": []},
            {"epoch": "war",   "active_conditions": ["northern_war_active"]},
        ]
        poller = WorldStatePoller(client, interval_s=999.0)
        poller._poll_once()
        poller._poll_once()
        _ = poller.pop_new_conditions()   # first call — drains the queue
        assert poller.pop_new_conditions() == []  # second call — empty
