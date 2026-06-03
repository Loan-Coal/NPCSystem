"""
Module: test_action_workers
Layer: demo_game (tests)
Purpose: Unit tests for action_workers background-thread functions.
Dependencies: demo_game.action_workers, unittest.mock, queue
Used by: make test-demo
"""

from __future__ import annotations

import queue
from unittest.mock import MagicMock, call, patch

import pytest

from demo_game.action_workers import bribe_worker, travel_worker
from demo_game.constants import BRIBE_GOLD_COST, BRIBE_STANDING_GAIN

_EXPECTED_STANDING = 10 + BRIBE_STANDING_GAIN


class TestBribeWorker:
    def _make_client(
        self,
        gold: int,
        current_standing: int,
        faction_id: str = "city_guard",
        location_id: str | None = "market_square",
        tick_id: int | None = 5,
    ) -> MagicMock:
        """Build a mock EngineClient with location + clock responses pre-wired."""
        client = MagicMock()
        client.get_node.return_value = {"currency_balance": gold}
        client.get_npc_reputation.return_value = [{"faction_id": faction_id, "standing": current_standing}]
        client.put_npc_reputation.return_value = {}
        client.patch_node.return_value = {}
        # Location and tick for the gossip-event path.
        if location_id is not None:
            client.get_graph_edges.return_value = [{"dst_id": location_id}]
        else:
            client.get_graph_edges.return_value = []
        if tick_id is not None:
            client.get_clock_state.return_value = {"data": {"tick_id": tick_id}}
        else:
            client.get_clock_state.side_effect = Exception("clock unavailable")
        expected = min(100, current_standing + BRIBE_STANDING_GAIN)
        client.adjust_npc_reputation.return_value = {"data": {"standing": expected}}
        return client

    def test_bribe_ok_uses_adjust_npc_reputation_with_location(self) -> None:
        """Happy path: adjust_npc_reputation is called with location + tick when available."""
        client = self._make_client(gold=100, current_standing=10)
        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        status, faction_id, new_standing = result_q.get_nowait()
        assert status == "ok"
        assert faction_id == "city_guard"
        assert new_standing == _EXPECTED_STANDING
        client.adjust_npc_reputation.assert_called_once_with(
            "player_1", "city_guard", BRIBE_STANDING_GAIN, "market_square", 5
        )
        client.put_npc_reputation.assert_not_called()
        client.patch_node.assert_called_once_with("Character", "player_1", {"currency_balance": 100 - BRIBE_GOLD_COST})

    def test_bribe_ok_falls_back_to_put_when_no_location(self) -> None:
        """When location lookup returns nothing, falls back to put_npc_reputation."""
        client = self._make_client(gold=100, current_standing=10, location_id=None)
        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        status, _, _ = result_q.get_nowait()
        assert status == "ok"
        client.adjust_npc_reputation.assert_not_called()
        client.put_npc_reputation.assert_called_once()

    def test_bribe_ok_falls_back_to_put_when_no_tick(self) -> None:
        """When clock state is unavailable, falls back to put_npc_reputation."""
        client = self._make_client(gold=100, current_standing=10, tick_id=None)
        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        status, _, _ = result_q.get_nowait()
        assert status == "ok"
        client.adjust_npc_reputation.assert_not_called()
        client.put_npc_reputation.assert_called_once()

    def test_bribe_standing_capped_at_100(self) -> None:
        """Standing is capped at 100 when current + gain would exceed it."""
        client = self._make_client(gold=100, current_standing=95)
        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        status, faction_id, new_standing = result_q.get_nowait()
        assert status == "ok"
        assert new_standing == 100

    def test_bribe_err_insufficient_gold(self) -> None:
        """Player with less than BRIBE_GOLD_COST gold gets an error, no API writes."""
        client = self._make_client(gold=BRIBE_GOLD_COST - 1, current_standing=0)
        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        item = result_q.get_nowait()
        assert item[0] == "err"
        assert item[1] == "captain_sorn"
        client.put_npc_reputation.assert_not_called()
        client.adjust_npc_reputation.assert_not_called()
        client.patch_node.assert_not_called()

    def test_bribe_ok_zero_starting_standing(self) -> None:
        """NPC faction not in reputation list defaults current standing to 0."""
        client = MagicMock()
        client.get_node.return_value = {"currency_balance": 100}
        client.get_npc_reputation.return_value = []  # no existing record
        client.get_graph_edges.return_value = [{"dst_id": "market_square"}]
        client.get_clock_state.return_value = {"data": {"tick_id": 1}}
        client.adjust_npc_reputation.return_value = {"data": {"standing": BRIBE_STANDING_GAIN}}
        client.patch_node.return_value = {}

        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        status, faction_id, new_standing = result_q.get_nowait()
        assert status == "ok"
        assert new_standing == BRIBE_STANDING_GAIN

    def test_bribe_err_api_failure_pushes_err(self) -> None:
        """If adjust_npc_reputation raises, worker pushes ("err", npc_id, exc)."""
        client = self._make_client(gold=100, current_standing=0)
        client.adjust_npc_reputation.side_effect = Exception("neo4j down")

        result_q: queue.Queue = queue.Queue()
        bribe_worker(client, "player_1", "captain_sorn", "city_guard", result_q)

        item = result_q.get_nowait()
        assert item[0] == "err"
        assert item[1] == "captain_sorn"


class TestTravelWorker:
    def test_travel_worker_ok_no_prior_location(self) -> None:
        """Player has no existing LOCATED_AT — just upsert and advance clock."""
        client = MagicMock()
        client.get_graph_edges.return_value = []
        client.upsert_edge.return_value = {}
        client.advance_clock.return_value = {}

        result_q: queue.Queue = queue.Queue()
        travel_worker(client, "player_1", "loc_tavern", result_q)

        status, loc = result_q.get_nowait()
        assert status == "ok"
        assert loc == "loc_tavern"
        client.delete_edge.assert_not_called()
        client.upsert_edge.assert_called_once_with("LOCATED_AT", "player_1", "loc_tavern", {})
        client.advance_clock.assert_called_once_with(delta_ticks=1)

    def test_travel_worker_ok_deletes_old_location(self) -> None:
        """Player already has a LOCATED_AT edge — it gets deleted before new one is set."""
        client = MagicMock()
        client.get_graph_edges.return_value = [{"dst_id": "loc_market_square"}]
        client.delete_edge.return_value = True
        client.upsert_edge.return_value = {}
        client.advance_clock.return_value = {}

        result_q: queue.Queue = queue.Queue()
        travel_worker(client, "player_1", "loc_tavern", result_q)

        status, loc = result_q.get_nowait()
        assert status == "ok"
        assert loc == "loc_tavern"
        client.delete_edge.assert_called_once_with("LOCATED_AT", "player_1", "loc_market_square")
        client.upsert_edge.assert_called_once_with("LOCATED_AT", "player_1", "loc_tavern", {})

    def test_travel_worker_skips_delete_if_already_at_target(self) -> None:
        """If existing edge is already to the target location, no delete is sent."""
        client = MagicMock()
        client.get_graph_edges.return_value = [{"dst_id": "loc_tavern"}]
        client.upsert_edge.return_value = {}
        client.advance_clock.return_value = {}

        result_q: queue.Queue = queue.Queue()
        travel_worker(client, "player_1", "loc_tavern", result_q)

        status, loc = result_q.get_nowait()
        assert status == "ok"
        client.delete_edge.assert_not_called()

    def test_travel_worker_upsert_failure_pushes_err(self) -> None:
        """If upsert_edge raises, worker pushes ("err", location_id, exc)."""
        client = MagicMock()
        client.get_graph_edges.return_value = []
        client.upsert_edge.side_effect = Exception("neo4j down")

        result_q: queue.Queue = queue.Queue()
        travel_worker(client, "player_1", "loc_tavern", result_q)

        item = result_q.get_nowait()
        assert item[0] == "err"
        assert item[1] == "loc_tavern"

    def test_travel_worker_advance_clock_failure_pushes_err(self) -> None:
        """If advance_clock raises, worker pushes err even if upsert succeeded."""
        client = MagicMock()
        client.get_graph_edges.return_value = []
        client.upsert_edge.return_value = {}
        client.advance_clock.side_effect = Exception("clock error")

        result_q: queue.Queue = queue.Queue()
        travel_worker(client, "player_1", "loc_tavern", result_q)

        item = result_q.get_nowait()
        assert item[0] == "err"
        assert item[1] == "loc_tavern"
