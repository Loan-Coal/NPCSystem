"""
Module: test_fetcher
Layer: demo_game.tests
Purpose: Unit tests for graph_panel.fetcher — fetch_snapshot and compute_delta.
Dependencies: unittest.mock, demo_game.graph_panel.fetcher, demo_game.client
Used by: pytest test suite
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClient
from demo_game.graph_panel.fetcher import (
    GraphDelta,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    compute_delta,
    fetch_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHAR_ROW = {"id": "mira", "name": "Mira the Herbalist"}
_LOC_ROW = {"id": "market", "name": "The Market"}
_FACTION_ROW = {"id": "merchants", "name": "Merchants Guild"}
_EVENT_ROW = {"id": "northern_war_begins", "name": "Northern War Begins"}
_WS_ROW = {"id": "ws_main", "time_of_day": "morning"}
_KNOWS_ROW = {"src_id": "captain_sorn", "dst_id": "northern_war_begins"}
_BELIEF_ROW = {"id": "b_mira_1", "content": "herbs heal wounds", "confidence": 90}
_GOAL_ROW = {"id": "g_mira_1", "description": "gather rare herbs", "urgency": 70}


def _empty_client() -> MagicMock:
    """Return a mock client where all graph calls return empty lists."""
    client = MagicMock(spec=EngineClient)
    client.get_graph_nodes.return_value = []
    client.get_graph_edges.return_value = []
    client.get_beliefs.return_value = []
    client.get_goals.return_value = []
    return client


def _char_client() -> MagicMock:
    """Return a mock client that yields one Character (mira) and one belief + one goal."""

    def _nodes(node_type: str, **_kwargs: object) -> list[dict]:
        return [_CHAR_ROW] if node_type == "Character" else []

    def _edges(edge_type: str, **_kwargs: object) -> list[dict]:
        return [_KNOWS_ROW] if edge_type == "KNOWS_ABOUT" else []

    client = MagicMock(spec=EngineClient)
    client.get_graph_nodes.side_effect = _nodes
    client.get_graph_edges.side_effect = _edges
    client.get_beliefs.return_value = [_BELIEF_ROW]
    client.get_goals.return_value = [_GOAL_ROW]
    return client


# ---------------------------------------------------------------------------
# TestFetchSnapshot
# ---------------------------------------------------------------------------


class TestFetchSnapshot:
    def test_calls_get_graph_nodes_for_character(self) -> None:
        client = _empty_client()
        fetch_snapshot(client)
        calls = [c.args[0] for c in client.get_graph_nodes.call_args_list]
        assert "Character" in calls

    def test_calls_get_graph_nodes_for_all_five_structural_types(self) -> None:
        client = _empty_client()
        fetch_snapshot(client)
        calls = {c.args[0] for c in client.get_graph_nodes.call_args_list}
        assert calls == {"Character", "Location", "Faction", "Event", "world_state"}

    def test_calls_get_graph_edges_for_knows_about(self) -> None:
        client = _empty_client()
        fetch_snapshot(client)
        calls = [c.args[0] for c in client.get_graph_edges.call_args_list]
        assert "KNOWS_ABOUT" in calls

    def test_calls_get_graph_edges_for_all_five_structural_types(self) -> None:
        client = _empty_client()
        fetch_snapshot(client)
        calls = {c.args[0] for c in client.get_graph_edges.call_args_list}
        assert calls == {"KNOWS_ABOUT", "STANDS_WITH", "OPPOSES", "MEMBER_OF", "RELATES_TO"}

    def test_node_type_set_from_fetch_call(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        char_nodes = [n for n in snapshot.nodes if n.node_type == "Character"]
        assert len(char_nodes) == 1
        assert char_nodes[0].id == "mira"

    def test_edge_type_set_from_fetch_call(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        ka_edges = [e for e in snapshot.edges if e.edge_type == "KNOWS_ABOUT"]
        assert len(ka_edges) == 1

    def test_node_id_extracted_from_id_field(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        ids = {n.id for n in snapshot.nodes}
        assert "mira" in ids

    def test_edge_src_dst_extracted_correctly(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        ka_edges = [e for e in snapshot.edges if e.edge_type == "KNOWS_ABOUT"]
        assert ka_edges[0].src_id == "captain_sorn"
        assert ka_edges[0].dst_id == "northern_war_begins"

    def test_returns_graphsnapshot_instance(self) -> None:
        client = _empty_client()
        result = fetch_snapshot(client)
        assert isinstance(result, GraphSnapshot)

    def test_empty_engine_returns_empty_snapshot(self) -> None:
        client = _empty_client()
        snapshot = fetch_snapshot(client)
        assert snapshot.nodes == ()
        assert snapshot.edges == ()

    def test_get_beliefs_called_for_each_character(self) -> None:
        client = _char_client()
        fetch_snapshot(client)
        client.get_beliefs.assert_called_once_with("mira")

    def test_belief_nodes_synthesized_as_graphnodes(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        belief_nodes = [n for n in snapshot.nodes if n.node_type == "Belief"]
        assert len(belief_nodes) == 1
        assert belief_nodes[0].id == "b_mira_1"

    def test_believes_edges_synthesized(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        believes_edges = [e for e in snapshot.edges if e.edge_type == "BELIEVES"]
        assert len(believes_edges) == 1
        assert believes_edges[0].src_id == "mira"
        assert believes_edges[0].dst_id == "b_mira_1"

    def test_get_goals_called_for_each_character(self) -> None:
        client = _char_client()
        fetch_snapshot(client)
        client.get_goals.assert_called_once_with("mira")

    def test_goal_nodes_synthesized_as_graphnodes(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        goal_nodes = [n for n in snapshot.nodes if n.node_type == "Goal"]
        assert len(goal_nodes) == 1
        assert goal_nodes[0].id == "g_mira_1"

    def test_pursues_edges_synthesized(self) -> None:
        client = _char_client()
        snapshot = fetch_snapshot(client)
        pursues_edges = [e for e in snapshot.edges if e.edge_type == "PURSUES"]
        assert len(pursues_edges) == 1
        assert pursues_edges[0].src_id == "mira"
        assert pursues_edges[0].dst_id == "g_mira_1"


# ---------------------------------------------------------------------------
# TestComputeDelta
# ---------------------------------------------------------------------------


def _node(node_id: str, node_type: str = "Character") -> GraphNode:
    return GraphNode(id=node_id, node_type=node_type)


def _edge(src: str, dst: str, etype: str = "KNOWS_ABOUT") -> GraphEdge:
    return GraphEdge(src_id=src, dst_id=dst, edge_type=etype)


def _snap(*nodes: GraphNode, edges: tuple[GraphEdge, ...] = ()) -> GraphSnapshot:
    return GraphSnapshot(nodes=nodes, edges=edges)


class TestComputeDelta:
    def test_none_prev_all_nodes_are_new(self) -> None:
        curr = _snap(_node("a"), _node("b"))
        delta = compute_delta(None, curr)
        assert set(delta.new_nodes) == set(curr.nodes)

    def test_none_prev_all_edges_are_new(self) -> None:
        curr = GraphSnapshot(edges=(_edge("a", "b"), _edge("b", "c")))
        delta = compute_delta(None, curr)
        assert set(delta.new_edges) == set(curr.edges)

    def test_new_edge_appears_in_delta(self) -> None:
        prev = GraphSnapshot()
        new_e = _edge("x", "y")
        curr = GraphSnapshot(edges=(new_e,))
        delta = compute_delta(prev, curr)
        assert new_e in delta.new_edges

    def test_no_change_produces_empty_delta(self) -> None:
        n = _node("a")
        e = _edge("a", "b")
        snap = GraphSnapshot(nodes=(n,), edges=(e,))
        delta = compute_delta(snap, snap)
        assert delta.new_nodes == ()
        assert delta.new_edges == ()

    def test_new_node_appears_in_delta(self) -> None:
        prev = GraphSnapshot()
        new_n = _node("z")
        curr = GraphSnapshot(nodes=(new_n,))
        delta = compute_delta(prev, curr)
        assert new_n in delta.new_nodes

    def test_only_new_items_in_delta(self) -> None:
        old_e1 = _edge("a", "b")
        old_e2 = _edge("b", "c")
        new_e = _edge("c", "d")
        prev = GraphSnapshot(edges=(old_e1, old_e2))
        curr = GraphSnapshot(edges=(old_e1, old_e2, new_e))
        delta = compute_delta(prev, curr)
        assert list(delta.new_edges) == [new_e]

    def test_returns_graphdelta_instance(self) -> None:
        result = compute_delta(GraphSnapshot(), GraphSnapshot())
        assert isinstance(result, GraphDelta)
