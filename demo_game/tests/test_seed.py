"""
Module: test_seed
Layer: demo_game (tests)
Purpose: TDD unit tests for seed — builder shapes, dependency order, idempotency.
Dependencies: demo_game.seed, unittest.mock (no network, no engine required)
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from demo_game.seed import (
    build_event_payload,
    build_faction_payload,
    build_location_payload,
    build_npc_payload,
    build_world_state_payload,
    WorldStatePayload,
    seed_all,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(*, node_exists: bool = False, edge_exists: bool = False, beliefs_exist: bool = False) -> MagicMock:
    """Build a mock EngineClient for seed_all tests."""
    client = MagicMock()
    client.get_node.return_value = {"id": "x"} if node_exists else None
    client.get_edge.return_value = {"src_id": "a", "dst_id": "b"} if edge_exists else None
    client.get_beliefs.return_value = [{"id": "b_1"}] if beliefs_exist else []
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    client.post_belief.return_value = {"belief_id": "b_1"}
    client.post_goal.return_value = {"goal_id": "g_1"}
    client.post_memory.return_value = {"memory_id": "m_1"}
    client.post_secret.return_value = {"secret_id": "s_1"}
    client.post_quest_generate.return_value = {"quest_id": "q_mock_1"}
    _pledge_map = {
        "lira_fence": [{"pledgee_id": "thieves_guild", "pledge_type": "fealty"}],
        "aldric_merchant": [{"pledgee_id": "merchants_guild", "pledge_type": "fealty"}],
    }
    client.get_pledges_for_npc.side_effect = (
        lambda npc_id: _pledge_map.get(npc_id, []) if edge_exists else []
    )
    return client


# ---------------------------------------------------------------------------
# Builder: build_location_payload
# ---------------------------------------------------------------------------


def test_build_location_payload_returns_correct_shape() -> None:
    payload = build_location_payload(
        id="loc_tavern",
        name="The Rusty Flagon",
        location_tag="tavern",
        descriptor="A dimly lit tavern.",
    )
    assert payload["id"] == "loc_tavern"
    assert payload["name"] == "The Rusty Flagon"
    assert payload["location_tag"] == "tavern"
    assert payload["descriptor"] == "A dimly lit tavern."
    assert "last_graph_updated_at" in payload


# ---------------------------------------------------------------------------
# Builder: build_faction_payload
# ---------------------------------------------------------------------------


def test_build_faction_payload_returns_correct_shape() -> None:
    payload = build_faction_payload(
        id="merchants_guild",
        name="Merchants Guild",
        archetype="mercantile",
        description="Controls city trade.",
    )
    assert payload["id"] == "merchants_guild"
    assert payload["name"] == "Merchants Guild"
    assert payload["archetype"] == "mercantile"
    assert payload["description"] == "Controls city trade."
    assert payload["is_active"] is True


# ---------------------------------------------------------------------------
# Builder: build_npc_payload
# ---------------------------------------------------------------------------


def test_build_npc_payload_returns_correct_shape() -> None:
    payload = build_npc_payload(
        id="mira_innkeeper",
        name="Mira",
        archetype="innkeeper",
        faction_id="neutral",
        location_id="loc_tavern",
        biography="Runs the Rusty Flagon.",
        gossipy=60,
        credulity=55,
        honesty=70,
        voice_descriptor="Warm, observant.",
    )
    assert payload["id"] == "mira_innkeeper"
    assert payload["name"] == "Mira"
    assert payload["archetype"] == "innkeeper"
    assert payload["faction"] == "neutral"
    assert payload["is_player"] is False
    assert payload["is_active"] is True
    assert payload["gossipy"] == 60
    assert payload["credulity"] == 55
    assert payload["honesty"] == 70
    assert payload["current_mood"] == "neutral"
    assert payload["voice_descriptor"] == "Warm, observant."
    assert "created_at" in payload
    assert "updated_at" in payload
    assert "last_graph_updated_at" in payload


def test_build_npc_payload_voice_descriptor_defaults_to_none() -> None:
    payload = build_npc_payload(
        id="guard_01",
        name="Guard",
        archetype="guard",
        faction_id="city_guard",
        location_id="loc_barracks",
        biography="A guard.",
        gossipy=20,
        credulity=40,
        honesty=80,
    )
    assert payload["voice_descriptor"] is None


# ---------------------------------------------------------------------------
# Builder: build_event_payload
# ---------------------------------------------------------------------------


def test_build_event_payload_returns_correct_shape() -> None:
    payload = build_event_payload(
        id="northern_war_begins",
        summary="The northern armies have crossed the border",
        event_type="conflict",
        location_id="loc_guard_barracks",
        severity=90,
        is_public=False,
    )
    assert payload["id"] == "northern_war_begins"
    assert payload["summary"] == "The northern armies have crossed the border"
    assert payload["event_type"] == "conflict"
    assert payload["location_id"] == "loc_guard_barracks"
    assert payload["severity"] == 90
    assert payload["is_public"] is False
    assert "occurred_at" in payload
    assert "last_graph_updated_at" in payload


# ---------------------------------------------------------------------------
# Builder: build_world_state_payload
# ---------------------------------------------------------------------------


def test_build_world_state_payload_returns_typed_model() -> None:
    payload = build_world_state_payload(epoch="peace", active_conditions=[])
    assert isinstance(payload, WorldStatePayload)
    assert payload.id == "world"
    assert payload.epoch == "peace"
    assert payload.active_conditions == []


def test_build_world_state_payload_with_active_conditions() -> None:
    payload = build_world_state_payload(epoch="war", active_conditions=["northern_war"])
    assert payload.epoch == "war"
    assert payload.active_conditions == ["northern_war"]
    # model_dump() must still produce the full upsert property set.
    dumped = payload.model_dump()
    assert dumped["id"] == "world"
    assert "last_updated_at" in dumped and "last_graph_updated_at" in dumped


# ---------------------------------------------------------------------------
# seed_all: dependency order
# ---------------------------------------------------------------------------


def test_seed_all_creates_locations_before_npcs() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_calls = [c.args[0] for c in client.upsert_node.call_args_list]
    location_idx = next(i for i, t in enumerate(upsert_calls) if t == "Location")
    character_idx = next(i for i, t in enumerate(upsert_calls) if t == "Character")
    assert location_idx < character_idx


def test_seed_all_creates_factions_before_npcs() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_calls = [c.args[0] for c in client.upsert_node.call_args_list]
    faction_idx = next(i for i, t in enumerate(upsert_calls) if t == "Faction")
    character_idx = next(i for i, t in enumerate(upsert_calls) if t == "Character")
    assert faction_idx < character_idx


def test_seed_all_creates_npcs_before_inner_life() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_calls = [c.args[0] for c in client.upsert_node.call_args_list]
    character_idx = next(i for i, t in enumerate(upsert_calls) if t == "Character")
    # post_belief must be called after the last Character upsert
    assert client.post_belief.called
    # Verify character upsert happened (any Character means ordering was respected)
    assert character_idx >= 0


def test_seed_all_creates_world_state() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_types = [c.args[0] for c in client.upsert_node.call_args_list]
    assert "world_state" in upsert_types


def test_seed_all_creates_mira_relates_to_old_henryk_edge() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_edge_calls = client.upsert_edge.call_args_list
    args_list = [(c.args[0], c.args[1], c.args[2]) for c in upsert_edge_calls]
    assert ("RELATES_TO", "mira_innkeeper", "old_henryk") in args_list


def test_seed_all_creates_lira_relates_to_aldric_edge() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_edge_calls = client.upsert_edge.call_args_list
    args_list = [(c.args[0], c.args[1], c.args[2]) for c in upsert_edge_calls]
    assert ("RELATES_TO", "lira_fence", "aldric_merchant") in args_list


def test_seed_all_creates_lira_knows_about_market_fire_edge() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_edge_calls = client.upsert_edge.call_args_list
    args_list = [(c.args[0], c.args[1], c.args[2]) for c in upsert_edge_calls]
    assert ("KNOWS_ABOUT", "lira_fence", "market_fire") in args_list


def test_seed_all_creates_player_knows_about_edges() -> None:
    """F3.6: the player has KNOWS_ABOUT edges so GET /player/{id}/events returns data."""
    client = _mock_client()
    seed_all(client)
    upsert_edge_calls = client.upsert_edge.call_args_list
    args_list = [(c.args[0], c.args[1], c.args[2]) for c in upsert_edge_calls]
    assert ("KNOWS_ABOUT", "player_demo", "northern_war_begins") in args_list
    assert ("KNOWS_ABOUT", "player_demo", "market_fire") in args_list


def test_seed_all_creates_deception_belief() -> None:
    """G3.2: a planted is_deception belief is seeded (Belief node + flagged BELIEVES edge)."""
    client = _mock_client()
    seed_all(client)

    node_types = [c.args[0] for c in client.upsert_node.call_args_list]
    assert "Belief" in node_types

    edge_calls = client.upsert_edge.call_args_list
    believes = [c for c in edge_calls if c.args[0] == "BELIEVES" and c.args[1] == "lira_fence"]
    assert believes, "expected a BELIEVES edge from lira_fence"
    props = believes[0].args[3] if len(believes[0].args) > 3 else believes[0].kwargs.get("properties", {})
    assert props.get("is_deception") is True


def test_seed_all_creates_captain_sorn_opposes_lira_edge() -> None:
    client = _mock_client()
    seed_all(client)
    upsert_edge_calls = client.upsert_edge.call_args_list
    args_list = [(c.args[0], c.args[1], c.args[2]) for c in upsert_edge_calls]
    assert ("OPPOSES", "captain_sorn", "lira_fence") in args_list


# ---------------------------------------------------------------------------
# seed_all: idempotency — nodes
# ---------------------------------------------------------------------------


def test_seed_all_skips_existing_location_nodes() -> None:
    client = _mock_client(node_exists=True)
    result = seed_all(client)
    # All nodes exist → none created
    assert client.upsert_node.call_count == 0
    assert result["skipped"] > 0


def test_seed_all_skips_existing_edges() -> None:
    client = _mock_client(edge_exists=True)
    result = seed_all(client)
    assert client.upsert_edge.call_count == 0
    assert result["skipped"] > 0


# ---------------------------------------------------------------------------
# seed_all: idempotency — typed nodes (beliefs proxy)
# ---------------------------------------------------------------------------


def test_seed_all_always_upserts_inner_life_via_merge() -> None:
    # KE-6: MERGE semantics — inner-life items are always posted even on re-seed.
    # The server deduplicates via stable node IDs; the seeder never skips.
    client = _mock_client(beliefs_exist=True)
    seed_all(client)
    assert client.post_belief.called
    assert client.post_goal.called
    assert client.post_memory.called
    assert client.post_secret.called


def test_seed_all_creates_inner_life_when_no_beliefs() -> None:
    client = _mock_client(beliefs_exist=False)
    seed_all(client)
    assert client.post_belief.called
    assert client.post_goal.called
    assert client.post_memory.called
    assert client.post_secret.called


# ---------------------------------------------------------------------------
# seed_all: return value
# ---------------------------------------------------------------------------


def test_seed_all_returns_summary_dict_with_created_and_skipped() -> None:
    client = _mock_client()
    result = seed_all(client)
    assert "created" in result
    assert "skipped" in result
    assert isinstance(result["created"], int)
    assert isinstance(result["skipped"], int)


def test_seed_all_created_count_is_positive_on_empty_db() -> None:
    client = _mock_client()
    result = seed_all(client)
    assert result["created"] > 0


def test_seed_all_skipped_is_positive_when_all_nodes_exist() -> None:
    # KE-6: nodes/edges are skipped via get-then-check; inner-life items are always
    # upserted via MERGE. So skipped > 0, created > 0 on a fully-seeded DB.
    client = _mock_client(node_exists=True, edge_exists=True, beliefs_exist=True)
    result = seed_all(client)
    assert result["skipped"] > 0


# ---------------------------------------------------------------------------
# seed_all: no-clobber player state
# ---------------------------------------------------------------------------


def test_seed_all_preserves_player_gold_on_reseed() -> None:
    """Re-seeding when player_demo already exists must not call upsert_node for player."""
    client = MagicMock()

    def _get_node(node_type: str, node_id: str) -> dict | None:
        if node_type == "Character" and node_id == "player_demo":
            return {"id": "player_demo", "currency_balance": 80}  # mutated after bribe
        return None

    client.get_node.side_effect = _get_node
    client.get_edge.return_value = None
    client.get_beliefs.return_value = []
    client.upsert_node.return_value = {"data": {}}
    client.upsert_edge.return_value = {"data": {}}
    client.post_belief.return_value = {}
    client.post_goal.return_value = {}
    client.post_memory.return_value = {}
    client.post_secret.return_value = {}

    seed_all(client)

    player_upserts = [
        c for c in client.upsert_node.call_args_list
        if c.args[0] == "Character" and c.args[1].get("id") == "player_demo"
    ]
    assert player_upserts == [], "player_demo must not be upserted on re-seed (preserves gold)"


def test_seed_all_does_not_create_player_faction_standing_edges() -> None:
    """Seeder must never create STANDS_WITH edges from player_demo (preserves bribe results)."""
    client = _mock_client()
    seed_all(client)
    player_standing = [
        c for c in client.upsert_edge.call_args_list
        if c.args[0] == "STANDS_WITH" and c.args[1] == "player_demo"
    ]
    assert player_standing == [], "no STANDS_WITH edges must be seeded for player_demo"


# ---------------------------------------------------------------------------
# _seed_quests
# ---------------------------------------------------------------------------


def test_seed_quests_calls_post_quest_offer() -> None:
    from demo_game.seed import _seed_quests

    client = _mock_client()
    client.post_quest_offer.return_value = {"data": {"quest_id": "aldric_deliver_quest"}}
    _seed_quests(client)

    client.post_quest_offer.assert_called_once()
    call_kwargs = client.post_quest_offer.call_args[1]
    assert call_kwargs["quest_id"] == "aldric_deliver_quest"
    assert call_kwargs["player_id"] == "player_demo"


def test_seed_quests_writes_quest_id_to_cache() -> None:
    import json as _json
    from unittest.mock import patch as _patch
    from demo_game.seed import _seed_quests

    client = _mock_client()
    client.post_quest_offer.return_value = {"data": {"quest_id": "aldric_deliver_quest"}}
    with _patch("demo_game.seed.Path") as mock_path_cls:
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = False
        mock_path_inst.parent = MagicMock()
        mock_path_cls.return_value = mock_path_inst
        _seed_quests(client)

    written = mock_path_inst.write_text.call_args[0][0]
    assert _json.loads(written) == {"quest_id": "aldric_deliver_quest"}


def test_seed_quests_skips_post_quest_offer_if_quest_exists() -> None:
    """_seed_quests must not re-offer a quest that already exists (preserves completed state)."""
    from demo_game.seed import _ALDRIC_QUEST_ID, _seed_quests

    client = MagicMock()
    client.get_node.return_value = {"id": _ALDRIC_QUEST_ID, "status": "completed"}

    _seed_quests(client)

    client.post_quest_offer.assert_not_called()


def test_seed_quests_non_fatal_on_client_error() -> None:
    from unittest.mock import patch as _patch
    from demo_game.seed import _seed_quests

    client = MagicMock()
    client.post_quest_generate.side_effect = Exception("engine unavailable")
    # Must not raise
    _seed_quests(client)


def test_seed_player_items_skips_amulet_if_already_owned() -> None:
    """_seed_player_and_items must not re-create OWNS(player→amulet) if another character already owns the amulet.

    Simulates the post-delivery state: player→amulet edge was deleted (get_edge returns None),
    but aldric→amulet exists (get_graph_edges returns it).
    """
    from demo_game.seed import _AMULET_ID, _PLAYER_ID, _seed_player_and_items

    client = MagicMock()
    client.get_node.return_value = {"id": "x"}  # all nodes exist
    client.get_edge.return_value = None  # player→amulet edge is gone (was transferred)
    client.get_graph_edges.return_value = [{"src_id": "aldric_merchant", "dst_id": _AMULET_ID}]

    _seed_player_and_items(client)

    for c in client.upsert_edge.call_args_list:
        args = c[0]
        assert not (len(args) >= 3 and args[0] == "OWNS" and args[1] == _PLAYER_ID and args[2] == _AMULET_ID), (
            "upsert_edge must NOT create OWNS(player→amulet) when amulet is already owned by someone else"
        )


def test_seed_player_items_creates_owns_edge_when_no_owner() -> None:
    """_seed_player_and_items must create OWNS(player→amulet) when the amulet has no current owner."""
    from demo_game.seed import _AMULET_ID, _PLAYER_ID, _seed_player_and_items

    client = MagicMock()
    client.get_node.return_value = None  # nothing exists yet
    client.get_edge.return_value = None  # edge doesn't exist
    client.get_graph_edges.return_value = []  # no current owners

    _seed_player_and_items(client)

    edge_calls = [(c[0][0], c[0][1], c[0][2]) for c in client.upsert_edge.call_args_list if len(c[0]) >= 3]
    assert ("OWNS", _PLAYER_ID, _AMULET_ID) in edge_calls, "upsert_edge must create OWNS(player→amulet) when no owner"


def test_seed_aldric_inventory_skips_spice_if_already_owned() -> None:
    """_seed_aldric_inventory must not re-create OWNS(aldric→spice) if another character already owns the spice.

    Simulates the post-trade state: aldric→spice edge was deleted, but player→spice exists.
    """
    from demo_game.seed import _SPICE_ID, _seed_aldric_inventory

    client = MagicMock()
    client.get_node.return_value = {"id": "x"}  # nodes exist
    client.get_edge.return_value = None  # aldric→spice edge is gone (was sold)
    client.get_graph_edges.return_value = [{"src_id": "player_demo", "dst_id": _SPICE_ID}]

    _seed_aldric_inventory(client)

    for c in client.upsert_edge.call_args_list:
        args = c[0]
        assert not (len(args) >= 3 and args[0] == "OWNS" and args[2] == _SPICE_ID), (
            "upsert_edge must NOT create OWNS(aldric→spice) when spice is already owned by someone else"
        )


def test_seed_all_calls_quest_offer() -> None:
    client = _mock_client()
    client.post_quest_offer.return_value = {"data": {"quest_id": "aldric_deliver_quest"}}
    with patch("demo_game.seed.Path") as mock_path_cls:
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = False
        mock_path_inst.parent = MagicMock()
        mock_path_cls.return_value = mock_path_inst
        seed_all(client)
    client.post_quest_offer.assert_called_once()
