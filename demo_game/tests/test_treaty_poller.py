"""
Module: test_treaty_poller
Layer: demo_game (tests)
Purpose: Unit tests for TreatyPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.treaty_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.client import EngineClientError
from demo_game.treaty_poller import TreatyPoller


def _make_client(
    per_faction: dict[str, list[dict]] | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values per faction."""
    client = MagicMock()
    if raises is not None:
        client.get_faction_treaties.side_effect = raises
    elif per_faction is not None:
        def _side_effect(faction_id: str) -> list[dict]:
            return per_faction.get(faction_id, [])
        client.get_faction_treaties.side_effect = _side_effect
    else:
        client.get_faction_treaties.return_value = []
    return client


_TREATY_A = {
    "id": "treaty_001",
    "parties": ["merchants_guild", "city_guard"],
    "terms_narrative": "Non-aggression pact.",
    "signed_at_tick": 1,
}
_TREATY_B = {
    "id": "treaty_002",
    "parties": ["thieves_guild", "merchants_guild"],
    "terms_narrative": "Smuggling tribute.",
    "signed_at_tick": 3,
}


class TestTreatyPollerInitialState:
    def test_initial_treaties_empty(self) -> None:
        """get_treaties() returns [] before any poll."""
        poller = TreatyPoller(_make_client(), interval_s=999.0)
        assert poller.get_treaties() == []


class TestTreatyPollerPollOnce:
    def test_poll_once_merges_treaties(self) -> None:
        """_poll_once fetches from all factions and merges results."""
        per_faction = {
            "merchants_guild": [_TREATY_A],
            "city_guard": [_TREATY_A],   # duplicate — same id
            "thieves_guild": [_TREATY_B],
        }
        client = _make_client(per_faction=per_faction)
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        treaties = poller.get_treaties()
        # TREATY_A appears only once (de-duplicated), plus TREATY_B
        assert len(treaties) == 2
        ids = {t["id"] for t in treaties}
        assert ids == {"treaty_001", "treaty_002"}

    def test_poll_once_empty_all_factions(self) -> None:
        """_poll_once stores empty list when all factions return empty."""
        client = _make_client()
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_treaties() == []

    def test_poll_once_swallows_engine_client_error(self) -> None:
        """_poll_once does not raise on EngineClientError; treaties stay empty."""
        client = _make_client(raises=EngineClientError("boom"))
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_treaties() == []

    def test_poll_once_swallows_generic_exception(self) -> None:
        """_poll_once does not raise on any Exception."""
        client = _make_client(raises=RuntimeError("network down"))
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_treaties() == []

    def test_poll_once_queries_all_demo_factions(self) -> None:
        """_poll_once calls get_faction_treaties for each DEMO_FACTIONS entry."""
        client = _make_client()
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        from demo_game.constants import DEMO_FACTIONS
        expected_calls = [call(f) for f in DEMO_FACTIONS]
        client.get_faction_treaties.assert_has_calls(expected_calls, any_order=False)


class TestTreatyPollerThreadSafety:
    def test_get_treaties_returns_copy(self) -> None:
        """get_treaties() returns a copy; mutating it does not affect state."""
        per_faction = {"merchants_guild": [_TREATY_A], "city_guard": [], "thieves_guild": []}
        client = _make_client(per_faction=per_faction)
        poller = TreatyPoller(client, interval_s=999.0)
        poller._poll_once()
        result = poller.get_treaties()
        result.append({"extra": True})
        assert poller.get_treaties() == [_TREATY_A]

    def test_refresh_sets_immediate_event(self) -> None:
        """refresh() sets the immediate event."""
        poller = TreatyPoller(_make_client(), interval_s=999.0)
        poller.refresh()
        assert poller._immediate.is_set()

    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that is alive."""
        poller = TreatyPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
