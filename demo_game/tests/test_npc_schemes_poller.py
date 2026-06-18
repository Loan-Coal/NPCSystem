"""
Module: test_npc_schemes_poller
Layer: demo_game (tests)
Purpose: Unit tests for NpcSchemesPoller (G2.2). No pygame, no network — all
         engine calls are mocked.
Dependencies: demo_game.npc_schemes_poller, unittest.mock
Used by: pytest
"""

from __future__ import annotations

from unittest.mock import MagicMock

from demo_game.npc_schemes_poller import NpcSchemesPoller

_SAMPLE = [
    {
        "scheme_id": "lira__abc",
        "goal": "rob the vault",
        "status": "discovered",
        "discovered": True,
        "steps": [{"step_order": 1, "completed": True, "summary": "cased it"}],
    }
]


def _make_client(schemes=None, raises=None) -> MagicMock:
    client = MagicMock()
    if raises is not None:
        client.get_schemes.side_effect = raises
    else:
        client.get_schemes.return_value = schemes if schemes is not None else []
    return client


def test_get_schemes_empty_before_poll() -> None:
    poller = NpcSchemesPoller(_make_client(), interval_s=999.0)
    assert poller.get_schemes() == []


def test_set_active_npc_stores_and_clears() -> None:
    client = _make_client(schemes=_SAMPLE)
    poller = NpcSchemesPoller(client, interval_s=999.0)
    poller.set_active_npc("lira_fence")
    poller._poll_once()
    assert poller.get_schemes() == _SAMPLE
    poller.set_active_npc("captain_sorn")
    assert poller.get_schemes() == []


def test_poll_once_no_npc_is_noop() -> None:
    client = _make_client(schemes=_SAMPLE)
    poller = NpcSchemesPoller(client, interval_s=999.0)
    poller._poll_once()
    client.get_schemes.assert_not_called()
    assert poller.get_schemes() == []


def test_poll_once_updates_schemes() -> None:
    poller = NpcSchemesPoller(_make_client(schemes=_SAMPLE), interval_s=999.0)
    poller.set_active_npc("lira_fence")
    poller._poll_once()
    assert poller.get_schemes() == _SAMPLE


def test_poll_error_is_swallowed() -> None:
    poller = NpcSchemesPoller(_make_client(raises=RuntimeError("boom")), interval_s=999.0)
    poller.set_active_npc("lira_fence")
    poller._poll_once()  # must not raise
    assert poller.get_schemes() == []


def test_get_schemes_returns_copy() -> None:
    poller = NpcSchemesPoller(_make_client(schemes=_SAMPLE), interval_s=999.0)
    poller.set_active_npc("lira_fence")
    poller._poll_once()
    snap = poller.get_schemes()
    snap.append({"injected": True})
    assert len(poller.get_schemes()) == 1
