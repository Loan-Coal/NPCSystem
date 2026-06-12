"""
Module: test_seed_h2
Layer: demo_game (tests)
Purpose: TDD tests for H2.2–H2.5 content expansion: 14 NPCs, 7 locations + districts,
         5 factions, 18 quests across 6 chains; verifies idempotency via KE-6.
Dependencies: demo_game.seed, demo_game.seed_npc_data, demo_game.constants,
              unittest.mock (no network, no engine required)
Used by: pytest demo_game/tests/ -q
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.constants import (
    DEMO_FACTIONS,
    FACTION_ID_CROWN_LOYALISTS,
    FACTION_ID_DOCKSIDE_SMUGGLERS,
    LOC_ID_DOCKS,
    LOC_ID_FORGE,
    LOC_ID_HARBOR_DISTRICT,
    LOC_ID_NORTH_GATE,
    LOC_ID_OLD_QUARTER,
    LOC_ID_TEMPLE,
    LOCATION_DISPLAY_NAMES,
    LOCATION_NPC_MAP,
    NPC_DISPLAY_NAMES,
    NPC_FACTIONS,
    WIN_QUEST_CHAIN_IDS,
)
from demo_game.seed import _NPCS, _LOCATIONS, seed_all
from demo_game.seed_npc_data import (
    H2_CHAIN_QUESTS,
    H2_FACTIONS,
    H2_LOCATIONS,
    H2_NPCS,
    H2_PART_OF_EDGES,
    H2_QUEST_UNLOCKS_CHAINS,
    H2_SOURCE_CHAIN_QUESTS,
    H2_WIN_QUEST_IDS,
    NPC_ID_BREN_SMITH,
    NPC_ID_DORN_DOCKMASTER,
    NPC_ID_GARRICK_DESERTER,
    NPC_ID_NESSA_PRIESTESS,
    NPC_ID_TILDA_HERBALIST,
    NPC_ID_VEX_SPYMASTER,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client_fresh() -> MagicMock:
    """Mock EngineClient simulating an empty database."""
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


def _mock_client_full() -> MagicMock:
    """Mock EngineClient simulating a fully-seeded database (all nodes/edges exist)."""
    client = MagicMock()
    client.get_node.return_value = {"id": "existing"}
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
    return client


# ---------------------------------------------------------------------------
# H2.2: cast expansion — 14 NPCs total
# ---------------------------------------------------------------------------


def test_h2_total_npc_count_is_14() -> None:
    """_NPCS (8 original) + H2_NPCS (6 new) must sum to 14 Character nodes."""
    total = len(_NPCS) + len(H2_NPCS)
    assert total == 14, f"Expected 14 NPCs total, got {total}"


def test_h2_new_npc_ids_present() -> None:
    """All 6 H2 NPC IDs must be in H2_NPCS."""
    h2_ids = {row[0] for row in H2_NPCS}
    expected = {
        NPC_ID_BREN_SMITH, NPC_ID_NESSA_PRIESTESS, NPC_ID_DORN_DOCKMASTER,
        NPC_ID_VEX_SPYMASTER, NPC_ID_TILDA_HERBALIST, NPC_ID_GARRICK_DESERTER,
    }
    assert expected == h2_ids


def test_h2_npcs_seeded_on_fresh_db() -> None:
    """seed_all must call upsert_node(Character, ...) for all 14 NPCs on an empty DB."""
    client = _mock_client_fresh()
    seed_all(client)
    seeded_character_ids = {
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Character"
    }
    for npc_id in (
        NPC_ID_BREN_SMITH, NPC_ID_NESSA_PRIESTESS, NPC_ID_DORN_DOCKMASTER,
        NPC_ID_VEX_SPYMASTER, NPC_ID_TILDA_HERBALIST, NPC_ID_GARRICK_DESERTER,
    ):
        assert npc_id in seeded_character_ids, (
            f"upsert_node not called for H2 NPC {npc_id!r}"
        )


def test_h2_all_14_npcs_seeded_on_fresh_db() -> None:
    """seed_all must upsert exactly 14 (or more due to player) Character nodes on empty DB."""
    client = _mock_client_fresh()
    seed_all(client)
    character_ids = [
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Character"
    ]
    # 14 NPCs + 1 player = 15 Character upserts on a fresh DB
    assert len(character_ids) >= 14, (
        f"Expected at least 14 Character upserts, got {len(character_ids)}: {character_ids}"
    )


def test_h2_new_npcs_in_npc_display_names() -> None:
    """All 6 new H2 NPC IDs must have entries in NPC_DISPLAY_NAMES."""
    for npc_id in (
        NPC_ID_BREN_SMITH, NPC_ID_NESSA_PRIESTESS, NPC_ID_DORN_DOCKMASTER,
        NPC_ID_VEX_SPYMASTER, NPC_ID_TILDA_HERBALIST, NPC_ID_GARRICK_DESERTER,
    ):
        assert npc_id in NPC_DISPLAY_NAMES, f"Missing display name for {npc_id!r}"


def test_h2_new_npcs_in_npc_factions() -> None:
    """All 6 new H2 NPC IDs must have entries in NPC_FACTIONS."""
    for npc_id in (
        NPC_ID_BREN_SMITH, NPC_ID_NESSA_PRIESTESS, NPC_ID_DORN_DOCKMASTER,
        NPC_ID_VEX_SPYMASTER, NPC_ID_TILDA_HERBALIST, NPC_ID_GARRICK_DESERTER,
    ):
        assert npc_id in NPC_FACTIONS, f"Missing NPC_FACTIONS entry for {npc_id!r}"


def test_h2_new_npcs_in_location_npc_map() -> None:
    """All 6 new H2 NPC IDs must appear somewhere in LOCATION_NPC_MAP."""
    all_npcs = {npc for npcs in LOCATION_NPC_MAP.values() for npc in npcs}
    for npc_id in (
        NPC_ID_BREN_SMITH, NPC_ID_NESSA_PRIESTESS, NPC_ID_DORN_DOCKMASTER,
        NPC_ID_VEX_SPYMASTER, NPC_ID_TILDA_HERBALIST, NPC_ID_GARRICK_DESERTER,
    ):
        assert npc_id in all_npcs, f"{npc_id!r} not in any LOCATION_NPC_MAP entry"


def test_h2_npc_inner_life_seeded_on_fresh_db() -> None:
    """seed_all must call post_belief, post_memory for all H2 NPCs."""
    client = _mock_client_fresh()
    seed_all(client)
    # 14 NPCs all have inner life; post_belief must be called
    assert client.post_belief.called
    assert client.post_memory.called
    assert client.post_secret.called


def test_h2_npcs_skipped_on_reseed() -> None:
    """seed_all must not call upsert_node for H2 NPCs when they already exist."""
    client = _mock_client_full()
    result = seed_all(client)
    assert client.upsert_node.call_count == 0
    assert result["skipped"] > 0


# ---------------------------------------------------------------------------
# H2.3: locations 4→7 + district tier
# ---------------------------------------------------------------------------


def test_h2_total_location_count_is_7() -> None:
    """_LOCATIONS (4) + H2_LOCATIONS (4 venues) minus overlap = 4+4=8 venue nodes, but
    the spec says 4→7 (not counting districts as venue-count).  The spec table says
    4→7 venues; districts are an extra tier.  _LOCATIONS has 4 original venues;
    H2_LOCATIONS has 4 new venues = 8 venues total.  Re-reading CONTENT_PLAN.md:
    '3 → 7 locations (+4)' means the *demo playable locations* reach 7.
    Original 3 + 4 new = 7 (not counting loc_chapel which was added in EXP-223 to reach 4).
    The ROADMAP says 4→7, so original 4 + 3 new venues (forge, temple, docks) + north_gate = 8.
    Spec says '+4 venues' which matches H2_LOCATIONS = 4 items.
    """
    # 4 original venues + 4 H2 venues = 8 total
    total = len(_LOCATIONS) + len(H2_LOCATIONS)
    assert total == 8, f"Expected 8 venue locations total, got {total}"


def test_h2_new_locations_in_h2_locations() -> None:
    """H2_LOCATIONS must contain forge, temple, docks, north_gate."""
    loc_ids = {row[0] for row in H2_LOCATIONS}
    assert LOC_ID_FORGE in loc_ids
    assert LOC_ID_TEMPLE in loc_ids
    assert LOC_ID_DOCKS in loc_ids
    assert LOC_ID_NORTH_GATE in loc_ids


def test_h2_districts_defined() -> None:
    """H2_DISTRICTS must contain old_quarter and harbor_district."""
    from demo_game.seed_npc_data import H2_DISTRICTS
    dist_ids = {row[0] for row in H2_DISTRICTS}
    assert LOC_ID_OLD_QUARTER in dist_ids
    assert LOC_ID_HARBOR_DISTRICT in dist_ids


def test_h2_part_of_edges_include_district_hierarchy() -> None:
    """H2_PART_OF_EDGES must include venue→district and district→city edges."""
    edge_pairs = {(child, parent) for child, parent, _ in H2_PART_OF_EDGES}
    # Venue → district
    assert (LOC_ID_FORGE, LOC_ID_OLD_QUARTER) in edge_pairs
    assert (LOC_ID_TEMPLE, LOC_ID_OLD_QUARTER) in edge_pairs
    assert (LOC_ID_DOCKS, LOC_ID_HARBOR_DISTRICT) in edge_pairs
    assert (LOC_ID_NORTH_GATE, LOC_ID_HARBOR_DISTRICT) in edge_pairs
    # District → city
    assert (LOC_ID_OLD_QUARTER, "loc_city") in edge_pairs
    assert (LOC_ID_HARBOR_DISTRICT, "loc_city") in edge_pairs


def test_h2_new_locations_seeded_on_fresh_db() -> None:
    """seed_all must call upsert_node(Location, ...) for all 4 new H2 venues."""
    client = _mock_client_fresh()
    seed_all(client)
    seeded_loc_ids = {
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Location"
    }
    for loc_id in (LOC_ID_FORGE, LOC_ID_TEMPLE, LOC_ID_DOCKS, LOC_ID_NORTH_GATE):
        assert loc_id in seeded_loc_ids, f"upsert_node not called for {loc_id!r}"


def test_h2_location_display_names_complete() -> None:
    """All H2 venue and district location IDs must be in LOCATION_DISPLAY_NAMES."""
    for loc_id in (
        LOC_ID_FORGE, LOC_ID_TEMPLE, LOC_ID_DOCKS, LOC_ID_NORTH_GATE,
        LOC_ID_OLD_QUARTER, LOC_ID_HARBOR_DISTRICT,
    ):
        assert loc_id in LOCATION_DISPLAY_NAMES, f"Missing display name for {loc_id!r}"


def test_h2_part_of_calls_issued_on_fresh_db() -> None:
    """seed_all must call post_part_of for H2 PART_OF edges on a fresh DB."""
    client = _mock_client_fresh()
    seed_all(client)
    assert client.post_part_of.called, "post_part_of was never called"


# ---------------------------------------------------------------------------
# H2.4: factions 3→5 alliable
# ---------------------------------------------------------------------------


def test_h2_faction_count_is_5_alliable() -> None:
    """H2_FACTIONS provides 2 new factions; combined with original 3 = 5 alliable."""
    assert len(H2_FACTIONS) == 2, f"Expected 2 new H2 factions, got {len(H2_FACTIONS)}"


def test_h2_new_faction_ids_correct() -> None:
    """H2_FACTIONS must contain crown_loyalists and dockside_smugglers."""
    faction_ids = {row[0] for row in H2_FACTIONS}
    assert FACTION_ID_CROWN_LOYALISTS in faction_ids
    assert FACTION_ID_DOCKSIDE_SMUGGLERS in faction_ids


def test_h2_factions_seeded_on_fresh_db() -> None:
    """seed_all must call upsert_node(Faction, ...) for both new H2 factions."""
    client = _mock_client_fresh()
    seed_all(client)
    seeded_faction_ids = {
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Faction"
    }
    assert FACTION_ID_CROWN_LOYALISTS in seeded_faction_ids, (
        "upsert_node not called for crown_loyalists"
    )
    assert FACTION_ID_DOCKSIDE_SMUGGLERS in seeded_faction_ids, (
        "upsert_node not called for dockside_smugglers"
    )


def test_h2_new_factions_not_in_demo_factions_win_path() -> None:
    """crown_loyalists and dockside_smugglers must NOT be in DEMO_FACTIONS (win path unchanged).

    The new factions are alliable but not win-eligible via the H1 faction-standing path.
    D3/H2.7 will parameterize per-world; DEMO_FACTIONS keeps the original 3.
    """
    assert FACTION_ID_CROWN_LOYALISTS not in DEMO_FACTIONS, (
        "crown_loyalists should not be in DEMO_FACTIONS (win-eligible) — "
        "it is alliable-but-not-win until H2.7 parameterizes per-world"
    )
    assert FACTION_ID_DOCKSIDE_SMUGGLERS not in DEMO_FACTIONS, (
        "dockside_smugglers should not be in DEMO_FACTIONS (win-eligible) — "
        "it is alliable-but-not-win until H2.7 parameterizes per-world"
    )


def test_h2_faction_stands_with_edges_seeded() -> None:
    """seed_all must create STANDS_WITH edges for the new H2 faction relations."""
    client = _mock_client_fresh()
    seed_all(client)
    edge_triples = {
        (c.args[0], c.args[1], c.args[2])
        for c in client.upsert_edge.call_args_list
        if len(c.args) >= 3
    }
    # crown_loyalists opposes iron_legion
    assert ("STANDS_WITH", FACTION_ID_CROWN_LOYALISTS, "iron_legion") in edge_triples
    # dockside_smugglers allies thieves_guild
    assert ("STANDS_WITH", FACTION_ID_DOCKSIDE_SMUGGLERS, "thieves_guild") in edge_triples
    # dockside_smugglers opposes city_guard
    assert ("STANDS_WITH", FACTION_ID_DOCKSIDE_SMUGGLERS, "city_guard") in edge_triples


# ---------------------------------------------------------------------------
# H2.5: quests 6→18 across 6 chains
# ---------------------------------------------------------------------------


def test_h2_source_chain_quest_count_is_6() -> None:
    """H2_SOURCE_CHAIN_QUESTS must contain exactly 6 new source quests."""
    assert len(H2_SOURCE_CHAIN_QUESTS) == 6, (
        f"Expected 6 H2 source quests, got {len(H2_SOURCE_CHAIN_QUESTS)}"
    )


def test_h2_chain_quest_count_is_6() -> None:
    """H2_CHAIN_QUESTS must contain exactly 6 new chain (successor) quests."""
    assert len(H2_CHAIN_QUESTS) == 6, (
        f"Expected 6 H2 chain quests, got {len(H2_CHAIN_QUESTS)}"
    )


def test_h2_unlocks_chain_count_is_6() -> None:
    """H2_QUEST_UNLOCKS_CHAINS must contain exactly 6 new UNLOCKS edges."""
    assert len(H2_QUEST_UNLOCKS_CHAINS) == 6, (
        f"Expected 6 H2 UNLOCKS chain pairs, got {len(H2_QUEST_UNLOCKS_CHAINS)}"
    )


def test_h2_new_quests_seeded_on_fresh_db() -> None:
    """seed_all must call upsert_node(Quest, ...) for all 12 new H2 quests."""
    client = _mock_client_fresh()
    seed_all(client)
    seeded_quest_ids = {
        c.args[1]["id"]
        for c in client.upsert_node.call_args_list
        if c.args[0] == "Quest"
    }
    for quest in H2_SOURCE_CHAIN_QUESTS + H2_CHAIN_QUESTS:
        assert quest["id"] in seeded_quest_ids, (
            f"upsert_node not called for H2 quest {quest['id']!r}"
        )


def test_h2_unlocks_edges_seeded_on_fresh_db() -> None:
    """seed_all must create all 6 new H2 UNLOCKS chain edges."""
    client = _mock_client_fresh()
    seed_all(client)
    unlocks_edges = [
        (c.args[1], c.args[2])
        for c in client.upsert_edge.call_args_list
        if len(c.args) >= 3 and c.args[0] == "UNLOCKS"
    ]
    for src_id, dst_id, _ in H2_QUEST_UNLOCKS_CHAINS:
        assert (src_id, dst_id) in unlocks_edges, (
            f"UNLOCKS edge {src_id!r}→{dst_id!r} not seeded"
        )


def test_h2_win_quest_ids_in_win_quest_chain_ids() -> None:
    """All 6 H2 chain-successor quest IDs must be present in WIN_QUEST_CHAIN_IDS."""
    for quest_id in H2_WIN_QUEST_IDS:
        assert quest_id in WIN_QUEST_CHAIN_IDS, (
            f"H2 win quest {quest_id!r} not in WIN_QUEST_CHAIN_IDS"
        )


def test_h2_total_win_quest_ids_count() -> None:
    """WIN_QUEST_CHAIN_IDS must contain 11 IDs (5 original + 6 H2)."""
    assert len(WIN_QUEST_CHAIN_IDS) == 11, (
        f"Expected 11 total win quest IDs (5 original + 6 H2), got {len(WIN_QUEST_CHAIN_IDS)}"
    )


def test_h2_unlocks_chains_have_on_outcome_complete() -> None:
    """All H2 UNLOCKS edges must use on_outcome='complete'."""
    for src_id, dst_id, on_outcome in H2_QUEST_UNLOCKS_CHAINS:
        assert on_outcome == "complete", (
            f"Expected on_outcome='complete' for {src_id}→{dst_id}, got {on_outcome!r}"
        )


# ---------------------------------------------------------------------------
# Idempotency: re-seeding on a full DB must skip all H2 content
# ---------------------------------------------------------------------------


def test_h2_all_content_skipped_on_reseed() -> None:
    """seed_all must not upsert any node when all nodes/edges already exist (idempotent)."""
    client = _mock_client_full()
    result = seed_all(client)
    assert client.upsert_node.call_count == 0, (
        f"upsert_node called {client.upsert_node.call_count} times on full DB — should be 0"
    )
    assert result["skipped"] > 0
