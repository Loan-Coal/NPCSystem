"""
Module: test_gold_poller
Layer: demo_game (tests)
Purpose: Unit tests for GoldPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.gold_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.gold_poller import GoldPoller


def _make_client(
    char: dict | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_node.side_effect = raises
    else:
        client.get_node.return_value = char
    return client


class TestGoldPollerInitialState:
    def test_gold_is_none_before_first_poll(self) -> None:
        """get_gold() returns None before any poll has completed."""
        poller = GoldPoller(_make_client(), "player_demo", interval_s=999.0)
        assert poller.get_gold() is None

    def test_player_id_stored(self) -> None:
        """Constructor stores the player ID."""
        poller = GoldPoller(_make_client(), "my_player", interval_s=1.0)
        assert poller._player_id == "my_player"

    def test_interval_stored(self) -> None:
        """Constructor stores the polling interval."""
        poller = GoldPoller(_make_client(), "p", interval_s=5.5)
        assert poller._interval_s == 5.5


class TestGoldPollerPollLogic:
    def _poll_once(self, poller: GoldPoller) -> None:
        """Call the internal _run body once, bypassing the sleep."""
        client = poller._client
        try:
            char = client.get_node("Character", poller._player_id)
            gold = int((char or {}).get("currency_balance") or 0)
            with poller._lock:
                poller._gold = gold
        except Exception:
            pass

    def test_polls_currency_balance(self) -> None:
        """After a poll, get_gold() returns the character's currency_balance."""
        client = _make_client(char={"id": "player_demo", "currency_balance": 75})
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 75

    def test_polls_zero_balance(self) -> None:
        """currency_balance of 0 returns 0, not None."""
        client = _make_client(char={"id": "player_demo", "currency_balance": 0})
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 0

    def test_missing_currency_balance_defaults_to_zero(self) -> None:
        """A character node without currency_balance field returns 0."""
        client = _make_client(char={"id": "player_demo"})
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 0

    def test_none_character_node_defaults_to_zero(self) -> None:
        """A None character node (404) returns 0."""
        client = _make_client(char=None)
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 0

    def test_api_error_leaves_gold_unchanged(self) -> None:
        """EngineClientError during poll leaves the previous gold value unchanged."""
        client = _make_client(raises=EngineClientError("server error"))
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() is None

    def test_api_error_preserves_previous_value(self) -> None:
        """After a successful poll followed by an error, gold retains the old value."""
        client = MagicMock()
        client.get_node.return_value = {"currency_balance": 40}
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 40
        client.get_node.side_effect = EngineClientError("down")
        self._poll_once(poller)
        assert poller.get_gold() == 40

    def test_gold_updates_on_change(self) -> None:
        """Polling twice with different balances returns the latest value."""
        client = MagicMock()
        client.get_node.return_value = {"currency_balance": 100}
        poller = GoldPoller(client, "player_demo", interval_s=999.0)
        self._poll_once(poller)
        assert poller.get_gold() == 100
        client.get_node.return_value = {"currency_balance": 60}
        self._poll_once(poller)
        assert poller.get_gold() == 60


class TestGoldPollerThreadSafety:
    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that polls and updates gold."""
        client = _make_client(char={"currency_balance": 55})
        poller = GoldPoller(client, "player_demo", interval_s=0.05)
        poller.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if poller.get_gold() is not None:
                break
            time.sleep(0.01)
        assert poller.get_gold() == 55

    def test_get_gold_is_thread_safe(self) -> None:
        """Concurrent reads from get_gold() do not raise."""
        client = _make_client(char={"currency_balance": 30})
        poller = GoldPoller(client, "player_demo", interval_s=0.01)
        poller.start()
        errors: list[Exception] = []

        def reader() -> None:
            for _ in range(50):
                try:
                    poller.get_gold()
                except Exception as exc:
                    errors.append(exc)
                time.sleep(0.001)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
        assert errors == []
