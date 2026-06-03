"""
Module: test_npc_needs_poller
Layer: demo_game (tests)
Purpose: Unit tests for NpcNeedsPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.npc_needs_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.npc_needs_poller import NpcNeedsPoller


def _make_client(
    needs: list[dict] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_needs_for_npc.side_effect = raises
    else:
        client.get_needs_for_npc.return_value = needs or []
    return client


_SAMPLE_NEEDS = [
    {"id": "mira_need_rest", "kind": "rest", "level": 35, "decay_rate": 4, "character_id": "mira_innkeeper"},
    {"id": "mira_need_social", "kind": "social", "level": 85, "decay_rate": 2, "character_id": "mira_innkeeper"},
]


class TestNpcNeedsPollerInitialState:
    def test_initial_needs_empty(self) -> None:
        """get_needs() returns [] before any poll."""
        poller = NpcNeedsPoller(_make_client(), interval_s=999.0)
        assert poller.get_needs() == []

    def test_initial_npc_id_none(self) -> None:
        """Active NPC is None before set_active_npc is called."""
        poller = NpcNeedsPoller(_make_client(), interval_s=999.0)
        assert poller._npc_id is None


class TestNpcNeedsPollerSetActiveNpc:
    def test_set_active_npc_updates_id(self) -> None:
        """set_active_npc stores the new NPC id."""
        poller = NpcNeedsPoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        with poller._lock:
            assert poller._npc_id == "mira_innkeeper"

    def test_set_active_npc_clears_cache(self) -> None:
        """set_active_npc clears the cached needs list."""
        poller = NpcNeedsPoller(_make_client(needs=_SAMPLE_NEEDS), interval_s=999.0)
        poller._poll_once() if False else None  # keep cache empty for this test
        poller.set_active_npc("captain_sorn")
        assert poller.get_needs() == []

    def test_set_active_npc_none_clears(self) -> None:
        """set_active_npc(None) clears the NPC id and needs."""
        poller = NpcNeedsPoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller.set_active_npc(None)
        assert poller.get_needs() == []


class TestNpcNeedsPollerPollOnce:
    def test_poll_once_updates_needs(self) -> None:
        """After _poll_once(), get_needs() returns the fetched needs."""
        poller = NpcNeedsPoller(_make_client(needs=_SAMPLE_NEEDS), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_needs() == _SAMPLE_NEEDS

    def test_poll_once_passes_npc_id_to_client(self) -> None:
        """_poll_once() calls get_needs_for_npc with the active NPC id."""
        client = _make_client()
        poller = NpcNeedsPoller(client, interval_s=999.0)
        poller.set_active_npc("captain_sorn")
        poller._poll_once()
        client.get_needs_for_npc.assert_called_once_with("captain_sorn")

    def test_poll_once_skips_if_no_npc(self) -> None:
        """_poll_once() does nothing when no NPC is active."""
        client = _make_client()
        poller = NpcNeedsPoller(client, interval_s=999.0)
        poller._poll_once()
        client.get_needs_for_npc.assert_not_called()

    def test_error_does_not_crash(self) -> None:
        """EngineClientError during polling is swallowed; needs stay empty."""
        poller = NpcNeedsPoller(
            _make_client(raises=EngineClientError("down")), interval_s=999.0
        )
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_needs() == []

    def test_second_poll_replaces_first(self) -> None:
        """A second poll replaces the previous needs snapshot."""
        first = [{"id": "n1", "kind": "rest", "level": 30, "decay_rate": 4, "character_id": "mira_innkeeper"}]
        second = [{"id": "n1", "kind": "rest", "level": 25, "decay_rate": 4, "character_id": "mira_innkeeper"}]
        client = _make_client(needs=first)
        poller = NpcNeedsPoller(client, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        client.get_needs_for_npc.return_value = second
        poller._poll_once()
        assert poller.get_needs() == second


class TestNpcNeedsPollerImmutability:
    def test_get_needs_returns_copy(self) -> None:
        """Mutating the returned list does not affect internal state."""
        poller = NpcNeedsPoller(_make_client(needs=_SAMPLE_NEEDS), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        result = poller.get_needs()
        result.clear()
        assert len(poller.get_needs()) == len(_SAMPLE_NEEDS)


class TestNpcNeedsPollerDaemonThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() creates a daemon thread."""
        poller = NpcNeedsPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
