"""
Tests for NpcInitiativePoller — the live proactive-hail path (G2.4).

The interactive window's idle-player hail (bubble + NPC highlight + input prefill, tested
in test_game_window.py) is fed by this poller draining GET /v1/dialogue/pending. These tests
lock the client integration: a poll fetches pending intents for the player and exposes them
via pop_pending(); errors are swallowed so the render loop never crashes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from demo_game.pollers.npc_initiative_poller import NpcInitiativePoller


def _intent(npc_id: str, score: float) -> dict:
    return {"npc_id": npc_id, "score": score, "trigger_type": "memory", "tick": 1}


def test_poll_once_buffers_pending_intents_for_player() -> None:
    """A poll calls get_pending_intents(player_id) and exposes the batch via pop_pending."""
    client = MagicMock()
    client.get_pending_intents.return_value = [_intent("mira_innkeeper", 0.9)]
    poller = NpcInitiativePoller(client=client, player_id="player_demo")

    poller._poll_once()

    client.get_pending_intents.assert_called_once_with("player_demo")
    drained = poller.pop_pending()
    assert drained == [_intent("mira_innkeeper", 0.9)]
    # second drain is empty — pop_pending is destructive
    assert poller.pop_pending() == []


def test_poll_once_swallows_client_error() -> None:
    """A client error during polling is swallowed (never crashes the render loop)."""
    client = MagicMock()
    client.get_pending_intents.side_effect = RuntimeError("engine down")
    poller = NpcInitiativePoller(client=client, player_id="player_demo")

    poller._poll_once()  # must not raise

    assert poller.pop_pending() == []


def test_empty_pending_leaves_buffer_empty() -> None:
    """No pending intents leaves the buffer empty."""
    client = MagicMock()
    client.get_pending_intents.return_value = []
    poller = NpcInitiativePoller(client=client, player_id="player_demo")

    poller._poll_once()

    assert poller.pop_pending() == []
