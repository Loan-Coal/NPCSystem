"""Tests for spread_rumor_worker in action_workers."""

from __future__ import annotations

import queue
from unittest.mock import MagicMock

import pytest

from demo_game.workers.action_workers import spread_rumor_worker
from demo_game.constants import SPREAD_RUMOR_TEXT, SPREAD_RUMOR_SEVERITY


def _make_client(
    tick_id: int | None = 10,
    spread_response: dict | None = None,
    spread_raises: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    if tick_id is None:
        # Return a response with no tick_id key — _get_current_tick returns None,
        # which spread_rumor_worker converts to 0 via `or 0` (EXP-93 / ISSUE-066).
        client.get_clock_state.return_value = {"data": {}}
    else:
        client.get_clock_state.return_value = {"data": {"tick_id": tick_id}}

    if spread_raises is not None:
        client.spread_rumor.side_effect = spread_raises
    else:
        client.spread_rumor.return_value = spread_response or {
            "data": {"event_id": "rumor_plant_mira_10", "npc_id": "mira_innkeeper"}
        }
    return client


class TestSpreadRumorWorker:
    def test_ok_pushes_event_id(self) -> None:
        client = _make_client()
        q: queue.Queue = queue.Queue()
        spread_rumor_worker(client, "mira_innkeeper", q)
        status, npc_id, event_id = q.get_nowait()
        assert status == "ok"
        assert npc_id == "mira_innkeeper"
        assert event_id == "rumor_plant_mira_10"

    def test_calls_spread_rumor_with_correct_args(self) -> None:
        client = _make_client(tick_id=7)
        q: queue.Queue = queue.Queue()
        spread_rumor_worker(client, "captain_sorn", q)
        client.spread_rumor.assert_called_once_with(
            target_npc_id="captain_sorn",
            rumor_text=SPREAD_RUMOR_TEXT,
            severity=SPREAD_RUMOR_SEVERITY,
            tick_id=7,
        )

    def test_falls_back_to_tick_zero_when_clock_unavailable(self) -> None:
        client = _make_client(tick_id=None)
        q: queue.Queue = queue.Queue()
        spread_rumor_worker(client, "old_henryk", q)
        _, kwargs = client.spread_rumor.call_args
        assert kwargs["tick_id"] == 0

    def test_err_on_api_failure(self) -> None:
        client = _make_client(spread_raises=Exception("network error"))
        q: queue.Queue = queue.Queue()
        spread_rumor_worker(client, "lira_fence", q)
        status, npc_id, exc = q.get_nowait()
        assert status == "err"
        assert npc_id == "lira_fence"
        assert isinstance(exc, Exception)

    def test_empty_event_id_still_pushes_ok(self) -> None:
        client = _make_client(spread_response={"data": {}})
        q: queue.Queue = queue.Queue()
        spread_rumor_worker(client, "aldric_merchant", q)
        status, npc_id, event_id = q.get_nowait()
        assert status == "ok"
        assert event_id == ""
