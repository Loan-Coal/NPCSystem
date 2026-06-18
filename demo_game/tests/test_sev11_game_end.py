"""
Module: test_sev11_game_end
Layer: demo_game (tests)
Purpose: Regression tests for SEV-11: lose reachable, attribution freeze, neutral bribe guard.
Dependencies: demo_game.game_end_checker, demo_game.game_end_poller, demo_game.game_controller
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.game_end_checker import (
    LOSE_LOCATION_ID,
    check_lose,
)
from demo_game.game_end_poller import GameEndPoller


# ---------------------------------------------------------------------------
# Lose condition: LOSE_LOCATION_ID must match the only resolving battle location
# ---------------------------------------------------------------------------


def test_lose_location_is_guard_barracks():
    """Iron Legion armies are seeded at loc_guard_barracks; lose must match."""
    assert LOSE_LOCATION_ID == "loc_guard_barracks"


def test_check_lose_guard_barracks_returns_true():
    assert check_lose(["loc_guard_barracks"]) is True


def test_check_lose_market_square_does_not_trigger():
    """Market square is no longer the lose location."""
    assert check_lose(["loc_market_square"]) is False


# ---------------------------------------------------------------------------
# Attribution: poller freezes arc_faction on first crossing, not later max
# ---------------------------------------------------------------------------


def _make_client(poll1_records: list[dict], poll2_records: list[dict]) -> MagicMock:
    client = MagicMock()
    client.get_graph_edges.return_value = []
    client.get_npc_reputation.side_effect = [poll1_records, poll2_records]
    return client


def test_poller_arc_faction_frozen_on_first_crossing():
    """merchants crosses threshold at poll-1; guard crosses higher at poll-2 → arc stays merchants."""
    client = _make_client(
        poll1_records=[
            {"faction_id": "merchants_guild", "standing": 55},
            {"faction_id": "city_guard", "standing": 0},
        ],
        poll2_records=[
            {"faction_id": "merchants_guild", "standing": 55},
            {"faction_id": "city_guard", "standing": 80},
        ],
    )
    poller = GameEndPoller(client=client, player_id="player1")

    poller._poll_once()
    assert poller._first_allied_faction == "merchants_guild"

    poller._poll_once()
    state = poller.get_state()
    assert state.arc_faction == "merchants_guild"


def test_poller_arc_faction_none_until_threshold():
    client = MagicMock()
    client.get_graph_edges.return_value = []
    client.get_npc_reputation.return_value = [
        {"faction_id": "merchants_guild", "standing": 30},
    ]
    poller = GameEndPoller(client=client, player_id="player1")
    poller._poll_once()
    assert poller._first_allied_faction is None
    assert poller.get_state().arc_faction is None


# ---------------------------------------------------------------------------
# Neutral bribe guard: spawn_bribe with neutral NPC is a no-op
# ---------------------------------------------------------------------------


def _make_controller() -> tuple:
    """Return (controller, status_calls) — controller wired to a mock client."""
    from demo_game.game_controller import ControllerCallbacks, GameController

    status_calls: list[str] = []
    callbacks = ControllerCallbacks(
        on_set_status=lambda text, _dur: status_calls.append(text),
    )
    client = MagicMock()
    controller = GameController(client=client, player_id="player1", callbacks=callbacks)
    return controller, status_calls


def test_spawn_bribe_neutral_npc_noop_no_thread():
    """Bribing mira_innkeeper (neutral) must not enqueue a bribe worker thread."""
    controller, status_calls = _make_controller()
    initial_qsize = controller._bribe_q.qsize()

    controller.spawn_bribe("mira_innkeeper")

    # Queue must not have grown (bribe_worker was never dispatched).
    assert controller._bribe_q.qsize() == initial_qsize


def test_spawn_bribe_neutral_npc_sets_status():
    """Bribing a neutral NPC shows a clear 'no faction' status message."""
    controller, status_calls = _make_controller()
    controller.spawn_bribe("mira_innkeeper")
    assert status_calls, "Expected a status message for neutral bribe attempt"
    assert "neutral" in status_calls[0].lower() or "no faction" in status_calls[0].lower()


def test_spawn_bribe_neutral_old_henryk_noop():
    """old_henryk is also neutral — same guard applies."""
    controller, status_calls = _make_controller()
    controller.spawn_bribe("old_henryk")
    assert status_calls, "Expected a status message"
    assert controller._bribe_q.qsize() == 0


def test_spawn_bribe_faction_npc_enqueues(monkeypatch):
    """Bribing aldric_merchant (merchants_guild) should start a bribe thread."""
    import threading

    controller, _ = _make_controller()
    spawned: list[bool] = []

    original_start = threading.Thread.start

    def fake_start(self: threading.Thread) -> None:
        spawned.append(True)
        # Don't actually run the thread — just record the spawn.

    monkeypatch.setattr(threading.Thread, "start", fake_start)
    controller.spawn_bribe("aldric_merchant")
    assert spawned, "Expected a bribe thread to be started for a faction NPC"
