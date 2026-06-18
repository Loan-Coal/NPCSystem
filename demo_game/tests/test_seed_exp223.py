"""
Module: test_seed_exp223
Layer: demo_game (tests)
Purpose: EXP-223 — assert the richer world seed includes new NPCs and location.
         RED phase: these tests fail before the new data is added to seed.py.
Dependencies: demo_game.seed, demo_game.constants, unittest.mock
Used by: pytest demo_game/tests/ -k seed -q
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.constants import (
    LOCATION_NPC_MAP,
    NPC_DISPLAY_NAMES,
    NPC_FACTIONS,
    NPC_LOCATION_MAP,
    NPC_ID_SERA_BARMAID,
    NPC_ID_HARWICK_GUARD,
    NPC_ID_NEL_PICKPOCKET,
    LOC_ID_CHAPEL,
)
from demo_game.seed import _NPCS, _LOCATIONS, seed_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client_fresh() -> MagicMock:
    """Mock EngineClient simulating an empty database (all creates)."""
    client = MagicMock()
    client.get_node.return_value = None
    client.get_edge.return_value = None
    client.get_beliefs.return_value = []
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    client.post_belief.return_value = {"belief_id": "b_1"}
    client.post_goal.return_value = {"goal_id": "g_1"}
    client.post_memory.return_value = {"memory_id": "m_1"}
    client.post_secret.return_value = {"secret_id": "s_1"}
    client.post_quest_generate.return_value = {"quest_id": "q_mock_1"}
    client.get_pledges_for_npc.return_value = []
    client.get_graph_edges.return_value = []
    return client


# ---------------------------------------------------------------------------
# EXP-223: new NPC ids present in _NPCS data
# ---------------------------------------------------------------------------


def test_exp223_sera_barmaid_in_npcs() -> None:
    """sera_barmaid must appear in the _NPCS seed list."""
    npc_ids = [row[0] for row in _NPCS]
    assert NPC_ID_SERA_BARMAID in npc_ids, (
        f"Expected {NPC_ID_SERA_BARMAID!r} in _NPCS; got {npc_ids}"
    )


def test_exp223_harwick_guard_in_npcs() -> None:
    """harwick_guard must appear in the _NPCS seed list."""
    npc_ids = [row[0] for row in _NPCS]
    assert NPC_ID_HARWICK_GUARD in npc_ids, (
        f"Expected {NPC_ID_HARWICK_GUARD!r} in _NPCS; got {npc_ids}"
    )


def test_exp223_nel_pickpocket_in_npcs() -> None:
    """nel_pickpocket must appear in the _NPCS seed list."""
    npc_ids = [row[0] for row in _NPCS]
    assert NPC_ID_NEL_PICKPOCKET in npc_ids, (
        f"Expected {NPC_ID_NEL_PICKPOCKET!r} in _NPCS; got {npc_ids}"
    )


# ---------------------------------------------------------------------------
# EXP-223: new location in _LOCATIONS data
# ---------------------------------------------------------------------------


def test_exp223_chapel_in_locations() -> None:
    """loc_chapel must appear in the _LOCATIONS seed list."""
    loc_ids = [row[0] for row in _LOCATIONS]
    assert LOC_ID_CHAPEL in loc_ids, (
        f"Expected {LOC_ID_CHAPEL!r} in _LOCATIONS; got {loc_ids}"
    )


# ---------------------------------------------------------------------------
# EXP-223: existing factions preserved (no new faction added)
# ---------------------------------------------------------------------------


def test_exp223_new_npcs_use_existing_factions() -> None:
    """New NPCs must be assigned to existing factions only — no new faction IDs."""
    allowed = {"merchants_guild", "city_guard", "thieves_guild", "neutral"}
    new_npc_ids = {NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET}
    npc_faction_map = {row[0]: row[3] for row in _NPCS}
    for npc_id in new_npc_ids:
        faction = npc_faction_map.get(npc_id)
        assert faction in allowed, (
            f"{npc_id} faction {faction!r} is not in allowed set {allowed}"
        )


# ---------------------------------------------------------------------------
# EXP-223: constants.py updated
# ---------------------------------------------------------------------------


def test_exp223_new_npc_ids_in_npc_display_names() -> None:
    """All three new NPC IDs must have entries in NPC_DISPLAY_NAMES."""
    for npc_id in (NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET):
        assert npc_id in NPC_DISPLAY_NAMES, (
            f"Missing display name for {npc_id!r}"
        )


def test_exp223_new_npc_ids_in_npc_factions() -> None:
    """All three new NPC IDs must have entries in NPC_FACTIONS."""
    for npc_id in (NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET):
        assert npc_id in NPC_FACTIONS, (
            f"Missing NPC_FACTIONS entry for {npc_id!r}"
        )


def test_exp223_new_npc_ids_in_location_npc_map() -> None:
    """All three new NPC IDs must appear somewhere in LOCATION_NPC_MAP."""
    all_npcs = {npc for npcs in LOCATION_NPC_MAP.values() for npc in npcs}
    for npc_id in (NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET):
        assert npc_id in all_npcs, (
            f"{npc_id!r} is not in any location in LOCATION_NPC_MAP"
        )


def test_exp223_chapel_in_location_display_names() -> None:
    """loc_chapel must have a display name in constants."""
    from demo_game.constants import LOCATION_DISPLAY_NAMES
    assert LOC_ID_CHAPEL in LOCATION_DISPLAY_NAMES, (
        f"Missing display name for {LOC_ID_CHAPEL!r}"
    )


# ---------------------------------------------------------------------------
# EXP-223: idempotency — new NPCs skipped on re-seed
# ---------------------------------------------------------------------------


def test_exp223_new_npcs_skipped_on_reseed() -> None:
    """seed_all must skip new NPC nodes when they already exist (idempotent)."""
    client = MagicMock()
    client.get_node.return_value = {"id": "existing"}  # all nodes exist
    client.get_edge.return_value = {"src_id": "a", "dst_id": "b"}
    client.get_beliefs.return_value = [{"id": "b_1"}]
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    client.post_belief.return_value = {}
    client.post_goal.return_value = {}
    client.post_memory.return_value = {}
    client.post_secret.return_value = {}
    client.get_pledges_for_npc.side_effect = lambda npc_id: [
        {"pledgee_id": "thieves_guild", "pledge_type": "fealty"},
        {"pledgee_id": "merchants_guild", "pledge_type": "fealty"},
    ]
    client.get_graph_edges.return_value = [{"src_id": "x", "dst_id": "y"}]

    result = seed_all(client)
    # All nodes exist → none should be upserted
    assert client.upsert_node.call_count == 0
    assert result["skipped"] > 0


# ---------------------------------------------------------------------------
# EXP-223: seed_all sends upsert_node calls for new NPCs on fresh DB
# ---------------------------------------------------------------------------


def test_exp223_seed_all_upserts_new_npcs_on_fresh_db() -> None:
    """seed_all must call upsert_node for all new NPCs when DB is empty."""
    client = _mock_client_fresh()
    seed_all(client)
    upsert_character_ids = [
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Character"
    ]
    for npc_id in (NPC_ID_SERA_BARMAID, NPC_ID_HARWICK_GUARD, NPC_ID_NEL_PICKPOCKET):
        assert npc_id in upsert_character_ids, (
            f"upsert_node was not called for {npc_id!r}"
        )


def test_exp223_seed_all_upserts_chapel_location_on_fresh_db() -> None:
    """seed_all must call upsert_node for loc_chapel when DB is empty."""
    client = _mock_client_fresh()
    seed_all(client)
    upsert_location_ids = [
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Location"
    ]
    assert LOC_ID_CHAPEL in upsert_location_ids, (
        f"upsert_node was not called for {LOC_ID_CHAPEL!r}"
    )
