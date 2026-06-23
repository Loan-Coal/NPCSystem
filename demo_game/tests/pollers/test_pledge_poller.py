"""
Module: test_pledge_poller
Layer: demo_game (tests)
Purpose: Unit tests for PledgePoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.pollers.pledge_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.pollers.pledge_poller import PledgePoller


def _make_client(
    pledges: list[dict] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_pledges_for_npc.side_effect = raises
    else:
        client.get_pledges_for_npc.return_value = pledges or []
    return client


_SAMPLE_PLEDGES = [
    {"pledgee_id": "thieves_guild", "pledge_type": "fealty", "tick": 0},
    {"pledgee_id": "mira_innkeeper", "pledge_type": "protect", "tick": 1},
]


class TestPledgePollerInitialState:
    def test_initial_pledges_empty(self) -> None:
        """get_pledges() returns [] before any poll."""
        poller = PledgePoller(_make_client(), interval_s=999.0)
        assert poller.get_pledges() == []

    def test_initial_npc_id_none(self) -> None:
        """Active NPC is None before set_active_npc is called."""
        poller = PledgePoller(_make_client(), interval_s=999.0)
        assert poller._npc_id is None


class TestPledgePollerSetActiveNpc:
    def test_set_active_npc_updates_id(self) -> None:
        """set_active_npc stores the new NPC id."""
        poller = PledgePoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("lira_fence")
        with poller._lock:
            assert poller._npc_id == "lira_fence"

    def test_set_active_npc_clears_pledge_cache(self) -> None:
        """set_active_npc clears the cached pledge list."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == _SAMPLE_PLEDGES

        poller.set_active_npc("captain_sorn")
        assert poller.get_pledges() == []

    def test_set_active_npc_none_clears_state(self) -> None:
        """set_active_npc(None) clears cached pledges and NPC id."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        poller.set_active_npc(None)
        assert poller.get_pledges() == []


class TestPledgePollerPollOnce:
    def test_poll_once_populates_pledges(self) -> None:
        """_poll_once updates pledges from the client."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == _SAMPLE_PLEDGES

    def test_poll_once_skips_when_no_npc(self) -> None:
        """_poll_once does not call the client when npc_id is None."""
        client = _make_client()
        poller = PledgePoller(client, interval_s=999.0)
        poller._poll_once()
        client.get_pledges_for_npc.assert_not_called()

    def test_poll_once_discards_stale_npc(self) -> None:
        """Results are discarded if the active NPC changed mid-request."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")

        def _switch_and_return(npc_id: str) -> list[dict]:
            poller._npc_id = "captain_sorn"
            return _SAMPLE_PLEDGES

        client.get_pledges_for_npc.side_effect = _switch_and_return
        poller._poll_once()
        assert poller.get_pledges() == []

    def test_poll_once_swallows_engine_client_error(self) -> None:
        """_poll_once does not raise on EngineClientError; cache stays empty."""
        client = _make_client(raises=EngineClientError("boom"))
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == []

    def test_poll_once_swallows_generic_exception(self) -> None:
        """_poll_once does not raise on any Exception; cache stays empty."""
        client = _make_client(raises=RuntimeError("network down"))
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == []


class TestPledgePollerThreadSafety:
    def test_get_pledges_returns_copy(self) -> None:
        """get_pledges() returns a copy; mutating it does not affect internal state."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = PledgePoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        result = poller.get_pledges()
        result.append({"extra": True})
        assert poller.get_pledges() == _SAMPLE_PLEDGES

    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that is alive."""
        poller = PledgePoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()

    def test_refresh_sets_immediate_event(self) -> None:
        """refresh() sets the immediate event to trigger early poll."""
        poller = PledgePoller(_make_client(), interval_s=999.0)
        poller.refresh()
        assert poller._immediate.is_set()
