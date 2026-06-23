"""
Module: test_quest_chain_seed
Layer: demo_game (tests)
Purpose: Verify that seed_all issues exactly 2 UNLOCKS edge upserts for the
    hand-authored quest chains in EXP-19.
Dependencies: demo_game.seeds.seed, unittest.mock (no network, no engine required)
Used by: pytest (make test-demo)

Does NOT: touch Neo4j, the NPC Engine API, or any real I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.seeds.seed import seed_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(*, node_exists: bool = False, edge_exists: bool = False) -> MagicMock:
    """Build a mock EngineClient for seed_all tests."""
    client = MagicMock()
    client.get_node.return_value = {"id": "x"} if node_exists else None
    client.get_edge.return_value = {"src_id": "a", "dst_id": "b"} if edge_exists else None
    client.get_beliefs.return_value = []
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    client.post_belief.return_value = {"belief_id": "b_1"}
    client.post_goal.return_value = {"goal_id": "g_1"}
    client.post_memory.return_value = {"memory_id": "m_1"}
    client.post_secret.return_value = {"secret_id": "s_1"}
    client.post_quest_generate.return_value = {"quest_id": "q_mock_1"}
    client.get_graph_edges.return_value = []
    _pledge_map: dict = {}
    client.get_pledges_for_npc.side_effect = lambda npc_id: _pledge_map.get(npc_id, [])
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_seed_all_creates_patrol_unlocks_captain_report_edge() -> None:
    """seed_all upserts UNLOCKS edge from demo_patrol_duty to demo_captain_report."""
    client = _mock_client()
    seed_all(client)

    upsert_calls = [str(c) for c in client.upsert_edge.call_args_list]
    unlocks_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args and c.args[0] == "UNLOCKS"
        or (c.kwargs and c.kwargs.get("edge_type") == "UNLOCKS")
    ]

    # Normalise: check positional or keyword args
    found = any(
        (
            len(c.args) >= 3
            and c.args[0] == "UNLOCKS"
            and c.args[1] == "demo_patrol_duty"
            and c.args[2] == "demo_captain_report"
        )
        for c in client.upsert_edge.call_args_list
    )
    assert found, (
        "Expected upsert_edge('UNLOCKS', 'demo_patrol_duty', 'demo_captain_report', ...) "
        f"but got calls: {upsert_calls}"
    )


def test_seed_all_creates_missing_goods_unlocks_fence_confrontation_edge() -> None:
    """seed_all upserts UNLOCKS edge from demo_missing_goods to demo_fence_confrontation."""
    client = _mock_client()
    seed_all(client)

    upsert_calls = [str(c) for c in client.upsert_edge.call_args_list]
    found = any(
        (
            len(c.args) >= 3
            and c.args[0] == "UNLOCKS"
            and c.args[1] == "demo_missing_goods"
            and c.args[2] == "demo_fence_confrontation"
        )
        for c in client.upsert_edge.call_args_list
    )
    assert found, (
        "Expected upsert_edge('UNLOCKS', 'demo_missing_goods', 'demo_fence_confrontation', ...) "
        f"but got calls: {upsert_calls}"
    )


def test_seed_all_creates_eight_unlocks_edges() -> None:
    """seed_all creates exactly 8 UNLOCKS edges: 2 original (EXP-19) + 6 new H2.5 chains."""
    client = _mock_client()
    seed_all(client)

    unlocks_calls = [
        c for c in client.upsert_edge.call_args_list
        if len(c.args) >= 1 and c.args[0] == "UNLOCKS"
    ]
    assert len(unlocks_calls) == 8, (
        f"Expected exactly 8 UNLOCKS upsert_edge calls (2 original + 6 H2.5), "
        f"got {len(unlocks_calls)}: {unlocks_calls}"
    )


def test_unlocks_edges_have_correct_on_outcome_property() -> None:
    """Both UNLOCKS edges are seeded with on_outcome='complete'."""
    client = _mock_client()
    seed_all(client)

    unlocks_calls = [
        c for c in client.upsert_edge.call_args_list
        if len(c.args) >= 1 and c.args[0] == "UNLOCKS"
    ]
    for c in unlocks_calls:
        # Properties are passed as 4th positional arg or kwargs
        props = c.args[3] if len(c.args) >= 4 else c.kwargs.get("properties", {})
        assert props.get("on_outcome") == "complete", (
            f"Expected on_outcome='complete' in UNLOCKS edge props, got: {props}"
        )
