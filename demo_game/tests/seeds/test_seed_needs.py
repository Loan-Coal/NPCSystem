"""
Module: test_seed_needs
Layer: demo_game (tests)
Purpose: TDD unit tests for needs seeding — verifies Need nodes and HAS_NEED
         edges are created for all seeded NPCs, and that SATISFIES_NEED edges
         wire locations to their respective Need nodes.
Dependencies: demo_game.seeds.seed_domain, demo_game.seeds.seed_world_data,
              demo_game.seeds.seed_npc_data, unittest.mock (no network required)
Used by: pytest demo_game/tests/seeds/
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.seeds.seed_domain import _seed_h2_npcs, _seed_needs
from demo_game.seeds.seed_npc_data import H2_NPC_NEEDS, H2_SATISFIES_NEED_EDGES
from demo_game.seeds.seed_world_data import _NPC_NEEDS, _SATISFIES_NEED_EDGES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client_fresh() -> MagicMock:
    """Mock EngineClient simulating an empty database (nothing exists yet)."""
    client = MagicMock()
    client.get_node.return_value = None
    client.get_edge.return_value = None
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    return client


def _mock_client_full() -> MagicMock:
    """Mock EngineClient simulating a fully-seeded database (all items exist)."""
    client = MagicMock()
    client.get_node.return_value = {"id": "existing"}
    client.get_edge.return_value = {"src_id": "a", "dst_id": "b"}
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    return client


# ---------------------------------------------------------------------------
# Data integrity tests (no client needed)
# ---------------------------------------------------------------------------


def test_npc_needs_non_empty() -> None:
    """_NPC_NEEDS must be populated — zero entries means need_decay has nothing."""
    assert len(_NPC_NEEDS) > 0, "_NPC_NEEDS is empty"


def test_h2_npc_needs_non_empty() -> None:
    """H2_NPC_NEEDS must be populated for H2 NPC need_decay to function."""
    assert len(H2_NPC_NEEDS) > 0, "H2_NPC_NEEDS is empty"


def test_gossip_path_npcs_have_needs() -> None:
    """Core gossip-path NPCs must have at least one need."""
    gossip_path: frozenset[str] = frozenset({"captain_sorn", "mira_innkeeper", "old_henryk"})
    npcs_with_needs = {entry[0] for entry in _NPC_NEEDS}
    missing = gossip_path - npcs_with_needs
    assert not missing, f"Gossip-path NPCs missing from _NPC_NEEDS: {missing}"


def test_need_ids_are_unique() -> None:
    """Every (npc_id, kind) pair must be unique to avoid duplicate Need nodes."""
    pairs = [(npc_id, kind) for npc_id, kind, _, _ in _NPC_NEEDS]
    assert len(pairs) == len(set(pairs)), "Duplicate (npc_id, kind) pairs in _NPC_NEEDS"


def test_h2_need_ids_are_unique() -> None:
    """Every (npc_id, kind) pair in H2_NPC_NEEDS must be unique."""
    pairs = [(npc_id, kind) for npc_id, kind, _, _ in H2_NPC_NEEDS]
    assert len(pairs) == len(set(pairs)), "Duplicate (npc_id, kind) pairs in H2_NPC_NEEDS"


def test_satisfies_need_edges_non_empty() -> None:
    """_SATISFIES_NEED_EDGES must be populated so need_decay is not one-directional."""
    assert len(_SATISFIES_NEED_EDGES) > 0, "_SATISFIES_NEED_EDGES is empty"


def test_h2_satisfies_need_edges_non_empty() -> None:
    """H2_SATISFIES_NEED_EDGES must be populated for H2 NPCs."""
    assert len(H2_SATISFIES_NEED_EDGES) > 0, "H2_SATISFIES_NEED_EDGES is empty"


def test_satisfies_need_edges_reference_known_need_ids() -> None:
    """Every need_id in _SATISFIES_NEED_EDGES must match a seeded Need node id."""
    expected_need_ids = {
        f"{npc_id}_need_{kind}" for npc_id, kind, _, _ in _NPC_NEEDS
    }
    for _loc_id, need_id, _mag in _SATISFIES_NEED_EDGES:
        assert need_id in expected_need_ids, (
            f"SATISFIES_NEED references unknown need_id {need_id!r}"
        )


def test_h2_satisfies_need_edges_reference_known_need_ids() -> None:
    """Every need_id in H2_SATISFIES_NEED_EDGES must match a seeded H2 Need node id."""
    expected_need_ids = {
        f"{npc_id}_need_{kind}" for npc_id, kind, _, _ in H2_NPC_NEEDS
    }
    for _loc_id, need_id, _mag in H2_SATISFIES_NEED_EDGES:
        assert need_id in expected_need_ids, (
            f"H2 SATISFIES_NEED references unknown need_id {need_id!r}"
        )


# ---------------------------------------------------------------------------
# _seed_needs behaviour tests (original NPCs)
# ---------------------------------------------------------------------------


def test_need_node_created_for_each_npc_need_on_fresh_db() -> None:
    """Every entry in _NPC_NEEDS must produce a 'Need' upsert_node call."""
    client = _mock_client_fresh()
    _seed_needs(client)

    need_upserts = [
        c for c in client.upsert_node.call_args_list
        if c.args[0] == "Need"
    ]
    created_ids = {c.args[1]["id"] for c in need_upserts}
    expected_ids = {f"{npc_id}_need_{kind}" for npc_id, kind, _, _ in _NPC_NEEDS}

    assert created_ids == expected_ids, (
        f"Missing Need node upserts for: {expected_ids - created_ids}"
    )


def test_has_need_edge_created_for_each_npc_need_on_fresh_db() -> None:
    """Every entry in _NPC_NEEDS must produce a HAS_NEED upsert_edge call."""
    client = _mock_client_fresh()
    _seed_needs(client)

    has_need_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "HAS_NEED"
    ]
    # Collect (character_id, need_id) pairs from the calls
    actual_pairs = {(c.args[1], c.args[2]) for c in has_need_calls}
    expected_pairs = {
        (npc_id, f"{npc_id}_need_{kind}")
        for npc_id, kind, _, _ in _NPC_NEEDS
    }

    assert actual_pairs == expected_pairs, (
        f"Missing HAS_NEED edges for: {expected_pairs - actual_pairs}"
    )


def test_satisfies_need_edge_created_for_each_entry_on_fresh_db() -> None:
    """Every entry in _SATISFIES_NEED_EDGES must produce a SATISFIES_NEED upsert_edge call."""
    client = _mock_client_fresh()
    _seed_needs(client)

    satisfies_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "SATISFIES_NEED"
    ]
    actual_pairs = {(c.args[1], c.args[2]) for c in satisfies_calls}
    expected_pairs = {(loc_id, need_id) for loc_id, need_id, _ in _SATISFIES_NEED_EDGES}

    assert actual_pairs == expected_pairs, (
        f"Missing SATISFIES_NEED edges for: {expected_pairs - actual_pairs}"
    )


def test_seed_needs_is_idempotent() -> None:
    """_seed_needs on a fully-seeded DB creates zero items."""
    client = _mock_client_full()
    count = _seed_needs(client)
    assert count == 0, f"Expected 0 on idempotent call, got {count}"


def test_seed_needs_returns_correct_count_on_fresh_db() -> None:
    """_seed_needs returns one count per Need node + one HAS_NEED + one per SATISFIES_NEED."""
    client = _mock_client_fresh()
    count = _seed_needs(client)
    expected = len(_NPC_NEEDS) * 2 + len(_SATISFIES_NEED_EDGES)
    assert count == expected, f"Expected {expected} items created, got {count}"


# ---------------------------------------------------------------------------
# H2 NPC HAS_NEED edge tests
# ---------------------------------------------------------------------------


def test_h2_has_need_edge_created_for_each_h2_need() -> None:
    """_seed_h2_npcs must produce a HAS_NEED edge for every entry in H2_NPC_NEEDS."""
    client = _mock_client_fresh()
    _seed_h2_npcs(client)

    has_need_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "HAS_NEED"
    ]
    actual_pairs = {(c.args[1], c.args[2]) for c in has_need_calls}
    expected_pairs = {
        (npc_id, f"{npc_id}_need_{kind}")
        for npc_id, kind, _, _ in H2_NPC_NEEDS
    }

    assert actual_pairs == expected_pairs, (
        f"Missing HAS_NEED edges for H2 NPCs: {expected_pairs - actual_pairs}"
    )


def test_h2_satisfies_need_edge_created_for_each_h2_satisfier() -> None:
    """_seed_h2_npcs must produce a SATISFIES_NEED edge for every H2_SATISFIES_NEED_EDGES entry."""
    client = _mock_client_fresh()
    _seed_h2_npcs(client)

    satisfies_calls = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "SATISFIES_NEED"
    ]
    actual_pairs = {(c.args[1], c.args[2]) for c in satisfies_calls}
    expected_pairs = {(loc_id, need_id) for loc_id, need_id, _ in H2_SATISFIES_NEED_EDGES}

    assert actual_pairs == expected_pairs, (
        f"Missing H2 SATISFIES_NEED edges: {expected_pairs - actual_pairs}"
    )
