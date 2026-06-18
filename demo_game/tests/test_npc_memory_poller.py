"""
Module: test_npc_memory_poller
Layer: demo_game (tests)
Purpose: Unit tests for NpcMemoryPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.npc_memory_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.npc_memory_poller import NpcMemoryPoller


def _make_client(
    memories: list[dict] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_memories.side_effect = raises
    else:
        client.get_memories.return_value = memories or []
    return client


_SAMPLE_MEMORIES = [
    {"id": "mem_1", "content": "The night a deserter came.", "vividness": 85, "emotional_charge": 65},
    {"id": "mem_2", "content": "Half my regulars never came back.", "vividness": 90, "emotional_charge": -75},
]


class TestNpcMemoryPollerInitialState:
    def test_initial_memories_empty(self) -> None:
        """get_memories() returns [] before any poll."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        assert poller.get_memories() == []

    def test_initial_npc_id_none(self) -> None:
        """Active NPC is None before set_active_npc is called."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        assert poller._npc_id is None


class TestNpcMemoryPollerSetActiveNpc:
    def test_set_active_npc_updates_id(self) -> None:
        """set_active_npc stores the new NPC id."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("aldric_merchant")
        with poller._lock:
            assert poller._npc_id == "aldric_merchant"

    def test_set_active_npc_clears_cache(self) -> None:
        """set_active_npc clears the cached memories list."""
        poller = NpcMemoryPoller(_make_client(memories=_SAMPLE_MEMORIES), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        poller.set_active_npc("captain_sorn")
        assert poller.get_memories() == []

    def test_set_active_npc_none_clears(self) -> None:
        """set_active_npc(None) clears the NPC id and memories."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller.set_active_npc(None)
        assert poller.get_memories() == []


class TestNpcMemoryPollerPollOnce:
    def test_poll_once_updates_memories(self) -> None:
        """After _poll_once(), get_memories() returns the fetched memories."""
        poller = NpcMemoryPoller(_make_client(memories=_SAMPLE_MEMORIES), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_memories() == _SAMPLE_MEMORIES

    def test_poll_once_passes_npc_id_to_client(self) -> None:
        """_poll_once() calls get_memories with the active NPC id."""
        client = _make_client()
        poller = NpcMemoryPoller(client, interval_s=999.0)
        poller.set_active_npc("lira_fence")
        poller._poll_once()
        client.get_memories.assert_called_once_with("lira_fence")

    def test_poll_once_skips_if_no_npc(self) -> None:
        """_poll_once() does nothing when no NPC is active."""
        client = _make_client()
        poller = NpcMemoryPoller(client, interval_s=999.0)
        poller._poll_once()
        client.get_memories.assert_not_called()

    def test_error_does_not_crash(self) -> None:
        """EngineClientError during polling is swallowed; memories stay empty."""
        poller = NpcMemoryPoller(
            _make_client(raises=EngineClientError("down")), interval_s=999.0
        )
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        assert poller.get_memories() == []

    def test_second_poll_replaces_first(self) -> None:
        """A second poll replaces the previous memories snapshot."""
        first = [{"id": "m1", "content": "old memory", "vividness": 50, "emotional_charge": 0}]
        second = [{"id": "m2", "content": "new memory", "vividness": 80, "emotional_charge": 20}]
        client = _make_client(memories=first)
        poller = NpcMemoryPoller(client, interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        client.get_memories.return_value = second
        poller._poll_once()
        assert poller.get_memories() == second


class TestNpcMemoryPollerImmutability:
    def test_get_memories_returns_copy(self) -> None:
        """Mutating the returned list does not affect internal state."""
        poller = NpcMemoryPoller(_make_client(memories=_SAMPLE_MEMORIES), interval_s=999.0)
        poller.set_active_npc("mira_innkeeper")
        poller._poll_once()
        result = poller.get_memories()
        result.clear()
        assert len(poller.get_memories()) == len(_SAMPLE_MEMORIES)


class TestNpcMemoryPollerRefresh:
    def test_refresh_signals_immediate_event(self) -> None:
        """refresh() sets the immediate event so the loop re-polls without waiting."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        assert not poller._immediate.is_set()
        poller.refresh()
        assert poller._immediate.is_set()


class TestNpcMemoryPollerDaemonThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() creates a daemon thread."""
        poller = NpcMemoryPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
