"""
Module: test_npc_player_model_poller
Layer: demo_game (tests)
Purpose: Unit tests for NpcPlayerModelPoller (G2.1).
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.pollers.npc_player_model_poller, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.pollers.npc_player_model_poller import NpcPlayerModelPoller

_PLAYER_ID = "player_demo"

_SAMPLE_MODEL = {
    "npc_id": "mira_innkeeper",
    "player_id": _PLAYER_ID,
    "perceived_trust": 72,
    "perceived_intent": "friendly",
    "last_updated_at": "2025-01-01T00:00:00Z",
}


def _make_client(
    model: dict | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_player_model.side_effect = raises
    else:
        client.get_player_model.return_value = model
    return client


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_get_model_returns_none_before_poll(self) -> None:
        """get_model() returns None before any poll."""
        poller = NpcPlayerModelPoller(_make_client(), _PLAYER_ID, interval_s=999.0)
        assert poller.get_model() is None

    def test_npc_id_none_initially(self) -> None:
        """Active NPC is None before set_active_npc is called."""
        poller = NpcPlayerModelPoller(_make_client(), _PLAYER_ID, interval_s=999.0)
        assert poller._npc_id is None


# ---------------------------------------------------------------------------
# set_active_npc
# ---------------------------------------------------------------------------


class TestSetActiveNpc:
    def test_stores_npc_id(self) -> None:
        """set_active_npc stores the new NPC id."""
        poller = NpcPlayerModelPoller(_make_client(), _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        with poller._lock:
            assert poller._npc_id == "mira_innkeeper"

    def test_clears_model_on_switch(self) -> None:
        """set_active_npc clears the cached model."""
        client = _make_client(model=_SAMPLE_MODEL)
        poller = NpcPlayerModelPoller(client, _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        poller.set_active_npc("captain_sorn")
        assert poller.get_model() is None

    def test_set_none_clears(self) -> None:
        """set_active_npc(None) clears npc id and model."""
        poller = NpcPlayerModelPoller(_make_client(), _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller.set_active_npc(None)
        assert poller.get_model() is None


# ---------------------------------------------------------------------------
# _poll_once
# ---------------------------------------------------------------------------


class TestPollOnce:
    def test_updates_model_on_success(self) -> None:
        """After _poll_once(), get_model() returns the fetched model."""
        poller = NpcPlayerModelPoller(_make_client(model=_SAMPLE_MODEL), _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_model() == _SAMPLE_MODEL

    def test_stores_none_when_404(self) -> None:
        """When engine returns None (404), model stays None."""
        poller = NpcPlayerModelPoller(_make_client(model=None), _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_model() is None

    def test_passes_npc_and_player_id(self) -> None:
        """_poll_once() calls get_player_model with the active NPC and player ids."""
        client = _make_client(model=_SAMPLE_MODEL)
        poller = NpcPlayerModelPoller(client, _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        client.get_player_model.assert_called_once_with("lira_fence", _PLAYER_ID)

    def test_skips_when_no_npc(self) -> None:
        """_poll_once() does nothing when no NPC is active."""
        client = _make_client()
        poller = NpcPlayerModelPoller(client, _PLAYER_ID, interval_s=999.0)
        poller._poll_once()
        client.get_player_model.assert_not_called()

    def test_error_does_not_crash(self) -> None:
        """Exceptions during polling are swallowed; model stays None."""
        poller = NpcPlayerModelPoller(
            _make_client(raises=Exception("network error")),
            _PLAYER_ID,
            interval_s=999.0,
        )
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_model() is None


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_get_model_returns_copy(self) -> None:
        """Mutating the returned dict does not affect internal state."""
        client = _make_client(model=_SAMPLE_MODEL)
        poller = NpcPlayerModelPoller(client, _PLAYER_ID, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        result = poller.get_model()
        assert result is not None
        result["perceived_trust"] = 0
        internal = poller.get_model()
        assert internal is not None
        assert internal["perceived_trust"] == _SAMPLE_MODEL["perceived_trust"]


# ---------------------------------------------------------------------------
# Daemon thread
# ---------------------------------------------------------------------------


class TestDaemonThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() creates a daemon thread."""
        poller = NpcPlayerModelPoller(_make_client(), _PLAYER_ID, interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
