"""
Module: test_npc_politics_poller
Layer: demo_game (tests)
Purpose: Unit tests for NpcPoliticsPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.pollers.npc_politics_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.pollers.npc_politics_poller import NpcPoliticsPoller


def _make_client(
    pledges: list[dict] | None = None,
    leverage: list[dict] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_pledges_for_npc.side_effect = raises
        client.get_leverage_for_npc.side_effect = raises
    else:
        client.get_pledges_for_npc.return_value = pledges or []
        client.get_leverage_for_npc.return_value = leverage or []
    return client


_SAMPLE_PLEDGES = [
    {"pledgee_id": "thieves_guild", "pledge_type": "fealty", "tick": 0},
]
_SAMPLE_LEVERAGE = [
    {"id": "lv_1", "demand": "Keep silent about the ledger", "status": "held", "created_at_tick": 0},
]


class TestNpcPoliticsPollerInitialState:
    def test_initial_pledges_empty(self) -> None:
        """get_pledges() returns [] before any poll."""
        poller = NpcPoliticsPoller(_make_client(), interval_s=999.0)
        assert poller.get_pledges() == []

    def test_initial_leverage_empty(self) -> None:
        """get_leverage() returns [] before any poll."""
        poller = NpcPoliticsPoller(_make_client(), interval_s=999.0)
        assert poller.get_leverage() == []

    def test_initial_npc_id_none(self) -> None:
        """Active NPC is None before set_active_npc is called."""
        poller = NpcPoliticsPoller(_make_client(), interval_s=999.0)
        assert poller._npc_id is None


class TestNpcPoliticsPollerSetActiveNpc:
    def test_set_active_npc_updates_id(self) -> None:
        """set_active_npc stores the new NPC id."""
        poller = NpcPoliticsPoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("lira_fence")
        with poller._lock:
            assert poller._npc_id == "lira_fence"

    def test_set_active_npc_clears_pledges_cache(self) -> None:
        """set_active_npc clears the cached pledges list."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == _SAMPLE_PLEDGES

        poller.set_active_npc("captain_sorn")
        assert poller.get_pledges() == []

    def test_set_active_npc_clears_leverage_cache(self) -> None:
        """set_active_npc clears the cached leverage list."""
        client = _make_client(leverage=_SAMPLE_LEVERAGE)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_leverage() == _SAMPLE_LEVERAGE

        poller.set_active_npc("captain_sorn")
        assert poller.get_leverage() == []

    def test_set_active_npc_none_clears_state(self) -> None:
        """set_active_npc(None) clears cached data and NPC id."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        poller.set_active_npc(None)
        assert poller.get_pledges() == []
        assert poller.get_leverage() == []


class TestNpcPoliticsPollerPollOnce:
    def test_poll_once_populates_pledges(self) -> None:
        """_poll_once updates pledges from the client."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == _SAMPLE_PLEDGES

    def test_poll_once_populates_leverage(self) -> None:
        """_poll_once updates leverage from the client."""
        client = _make_client(leverage=_SAMPLE_LEVERAGE)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_leverage() == _SAMPLE_LEVERAGE

    def test_poll_once_skips_when_no_npc(self) -> None:
        """_poll_once does not call the client when npc_id is None."""
        client = _make_client()
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller._poll_once()
        client.get_pledges_for_npc.assert_not_called()
        client.get_leverage_for_npc.assert_not_called()

    def test_poll_once_discards_stale_npc(self) -> None:
        """Results are discarded if the active NPC changed mid-request."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
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
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == []
        assert poller.get_leverage() == []

    def test_poll_once_swallows_generic_exception(self) -> None:
        """_poll_once does not raise on any Exception; cache stays empty."""
        client = _make_client(raises=RuntimeError("network down"))
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        assert poller.get_pledges() == []


class TestNpcPoliticsPollerThreadSafety:
    def test_get_pledges_returns_copy(self) -> None:
        """get_pledges() returns a copy; mutating it does not affect internal state."""
        client = _make_client(pledges=_SAMPLE_PLEDGES)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        result = poller.get_pledges()
        result.append({"extra": True})
        assert poller.get_pledges() == _SAMPLE_PLEDGES

    def test_get_leverage_returns_copy(self) -> None:
        """get_leverage() returns a copy; mutating it does not affect internal state."""
        client = _make_client(leverage=_SAMPLE_LEVERAGE)
        poller = NpcPoliticsPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        result = poller.get_leverage()
        result.append({"extra": True})
        assert poller.get_leverage() == _SAMPLE_LEVERAGE

    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that is alive."""
        poller = NpcPoliticsPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
