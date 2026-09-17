"""
Module: seed_domain
Layer: demo_game (external client)
Purpose: Domain-specific seeder helpers that orchestrate node/edge creation for
         characters, locations, quests, items, and the H2 content expansion.
         Each function is idempotent; all I/O goes through seed_io primitives.
Dependencies: demo_game.seeds.seed_builders, demo_game.seeds.seed_io,
              demo_game.seeds.seed_world_data, demo_game.seeds.seed_npc_data,
              demo_game.client (TYPE_CHECKING only)
Used by: demo_game.seeds.seed
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from demo_game.seeds.seed_builders import (
    _GAME_TIME,
    _PLAYER_STARTING_GOLD,
    _now,
    build_faction_payload,
    build_location_payload,
    build_npc_payload,
)
from demo_game.seeds.seed_io import (
    _seed_edge,
    _seed_item_edge_if_unowned,
    _seed_npc_inner_life,
    _seed_node,
)
from demo_game.seeds.seed_npc_data import (
    H2_CHAIN_QUESTS,
    H2_DISTRICTS,
    H2_FACTION_STANDS_WITH,
    H2_FACTIONS,
    H2_LOCATIONS,
    H2_NPC_INNER_LIFE,
    H2_NPC_LOCATED_AT,
    H2_NPC_MEMBER_OF,
    H2_NPC_NEEDS,
    H2_NPCS,
    H2_PART_OF_EDGES,
    H2_QUEST_UNLOCKS_CHAINS,
    H2_SATISFIES_NEED_EDGES,
    H2_SOURCE_CHAIN_QUESTS,
)
from demo_game.seeds.seed_world_data import (
    _AMULET_ID,
    _ALDRIC_QUEST_ID,
    _ALDRIC_REWARD_AMOUNT,
    _CHAIN_QUESTS,
    _DECEPTION_BELIEF_CONTENT,
    _DECEPTION_BELIEF_ID,
    _DECEPTION_BELIEF_NPC,
    _DECEPTION_GOAL_ID,
    _NPC_NEEDS,
    _PLAYER_ID,
    _QUEST_UNLOCKS_CHAINS,
    _SATISFIES_NEED_EDGES,
    _SCHEDULES,
    _SOURCE_CHAIN_QUESTS,
    _SPICE_ID,
    _SPICE_VALUE,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

# Re-export _PLAYER_STARTING_GOLD to avoid circular import in seed.py
__all__ = [
    "_seed_location_hierarchy",
    "_seed_h2_npcs",
    "_seed_h2_factions",
    "_seed_h2_quests",
    "_seed_deception_belief",
    "_seed_player_and_items",
    "_seed_aldric_inventory",
    "_seed_aldric_currency",
    "_seed_needs",
    "_seed_quests",
    "_seed_source_chain_quests",
    "_seed_chain_quests",
    "_seed_schedules",
    "_seed_quest_unlocks_chains",
]

logger = logging.getLogger(__name__)


def _seed_location_hierarchy(client: EngineClient) -> int:
    """Seed the city-level location hierarchy for the demo world (EXP-87).

    Creates a ``loc_city`` Location node and wires the existing demo
    locations into it via PART_OF edges. H2.3: also seeds district nodes
    and wires new venues into their districts. All calls use MERGE semantics
    so this function is idempotent on repeated runs.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of items created or upserted.
    """
    from demo_game.constants import LOC_ID_CHAPEL

    created = 0
    _seed_node(
        client,
        "Location",
        build_location_payload(
            id="loc_city",
            name="The City",
            location_tag="city",
            descriptor="The city that contains the tavern, market, and barracks.",
        ),
    )
    created += 1

    # Original venues directly under loc_city (EXP-87, EXP-223)
    _direct_venues = ["loc_tavern", "loc_market_square", "loc_guard_barracks", LOC_ID_CHAPEL]
    for child_id in _direct_venues:
        client.post_part_of(child_id, "loc_city", hierarchy_level=0)
        logger.info("  upserted PART_OF %s → loc_city", child_id)
    created += len(_direct_venues)

    # H2.3: district nodes (hierarchy_level=1 between venues and city)
    for dist_id, dist_name, dist_tag, dist_desc in H2_DISTRICTS:
        _seed_node(client, "Location", build_location_payload(dist_id, dist_name, dist_tag, dist_desc))
        created += 1

    # H2.3: venue → district → city PART_OF edges
    for child_id, parent_id, level in H2_PART_OF_EDGES:
        client.post_part_of(child_id, parent_id, hierarchy_level=level)
        logger.info("  upserted PART_OF %s → %s (level=%d)", child_id, parent_id, level)
    created += len(H2_PART_OF_EDGES)

    return created


def _seed_h2_npcs(client: EngineClient) -> int:
    """Seed the 6 H2.2 new NPCs with their inner-life data.

    Idempotent: skips NPCs whose Character node already exists.
    Non-fatal: logs a warning and continues on any single NPC error.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of items created.
    """
    created = 0
    for npc_tuple in H2_NPCS:
        npc_id = npc_tuple[0]
        try:
            payload = build_npc_payload(*npc_tuple)
            result = _seed_node(client, "Character", payload)
            if result == "created":
                created += 1
        except Exception as exc:
            logger.warning("[seed] H2 NPC %s skipped: %s", npc_id, exc)

    # MEMBER_OF edges for new NPCs
    for npc_id, faction_id, role in H2_NPC_MEMBER_OF:
        result = _seed_edge(client, "MEMBER_OF", npc_id, faction_id, {
            "role": role,
            "status": "active",
            "joined_at": _now(),
        })
        if result == "created":
            created += 1

    # LOCATED_AT edges for new NPCs
    for npc_id, loc_id in H2_NPC_LOCATED_AT:
        result = _seed_edge(client, "LOCATED_AT", npc_id, loc_id, {
            "is_permanent_resident": True,
            "arrived_at": _now(),
        })
        if result == "created":
            created += 1

    # Inner life
    for npc_id, life in H2_NPC_INNER_LIFE.items():
        n = _seed_npc_inner_life(
            client,
            npc_id,
            beliefs=life["beliefs"],
            goals=life["goals"],
            memories=life["memories"],
            secret=life["secret"],
        )
        created += n

    # Needs: nodes + HAS_NEED edges
    for npc_id, kind, level, decay_rate in H2_NPC_NEEDS:
        node_id = f"{npc_id}_need_{kind}"
        result = _seed_node(client, "Need", {
            "id": node_id,
            "kind": kind,
            "level": level,
            "decay_rate": decay_rate,
            "character_id": npc_id,
        })
        if result == "created":
            created += 1
        result = _seed_edge(client, "HAS_NEED", npc_id, node_id, {})
        if result == "created":
            created += 1

    # SATISFIES_NEED edges: wire H2 locations to H2 Need nodes
    for loc_id, need_id, magnitude in H2_SATISFIES_NEED_EDGES:
        result = _seed_edge(client, "SATISFIES_NEED", loc_id, need_id, {"magnitude": magnitude})
        if result == "created":
            created += 1

    return created


def _seed_h2_factions(client: EngineClient) -> int:
    """Seed the 2 H2.4 new factions (crown_loyalists, dockside_smugglers).

    Idempotent: skips Faction nodes that already exist.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of items created.
    """
    created = 0
    for faction_id, name, archetype, description in H2_FACTIONS:
        result = _seed_node(
            client, "Faction",
            build_faction_payload(faction_id, name, archetype, description),
        )
        if result == "created":
            created += 1

    for src_faction, dst_faction, standing in H2_FACTION_STANDS_WITH:
        result = _seed_edge(client, "STANDS_WITH", src_faction, dst_faction, {
            "standing": standing,
            "last_changed_at": "tick_0",
        })
        if result == "created":
            created += 1

    return created


def _seed_h2_quests(client: EngineClient) -> int:
    """Seed the 12 H2.5 new quest nodes and 6 UNLOCKS chain edges.

    Creates source quests, chain quests, and UNLOCKS edges.
    Idempotent: skips Quest nodes and edges that already exist.
    Non-fatal: logs a warning and continues on any single quest error.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of items created.
    """
    created = 0

    for quest in H2_SOURCE_CHAIN_QUESTS:
        quest_id = quest["id"]
        try:
            result = _seed_node(client, "Quest", {**quest, "created_at": _now()})
            if result == "created":
                created += 1
                logger.info("[seed] H2 source quest seeded: %s", quest_id)
            # Always seed edge: Quest may exist but edge may be missing from a partial prior run.
            _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
        except Exception as exc:
            logger.warning("[seed] H2 source quest %s skipped: %s", quest_id, exc)

    for quest in H2_CHAIN_QUESTS:
        quest_id = quest["id"]
        try:
            result = _seed_node(client, "Quest", {**quest, "created_at": _now()})
            if result == "created":
                created += 1
                logger.info("[seed] H2 chain quest seeded: %s", quest_id)
            # Always seed edge: Quest may exist but edge may be missing from a partial prior run.
            _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
        except Exception as exc:
            logger.warning("[seed] H2 chain quest %s skipped: %s", quest_id, exc)

    for src_id, dst_id, on_outcome in H2_QUEST_UNLOCKS_CHAINS:
        result = _seed_edge(
            client, "UNLOCKS", src_id, dst_id,
            {"on_outcome": on_outcome},
        )
        if result == "created":
            created += 1

    return created


def _seed_deception_belief(client: EngineClient) -> int:
    """Seed a planted is_deception belief held by an NPC (G3.2).

    Creates a Belief node and a BELIEVES edge flagged is_deception=true so the
    deception "tell" (G2.5) and the anti-hallucination eval (F3.3) have data, and the
    intrigue arc (G3.1) has a lie to reveal. Idempotent via _seed_node/_seed_edge.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of nodes/edges created.
    """
    created = 0
    belief_node = {
        "id": _DECEPTION_BELIEF_ID,
        "content": _DECEPTION_BELIEF_CONTENT,
        "confidence": 80,
        "created_at_game_time": json.dumps(_GAME_TIME),
    }
    if _seed_node(client, "Belief", belief_node) == "created":
        created += 1
    edge_props = {
        "is_deception": True,
        "deception_goal_id": _DECEPTION_GOAL_ID,
        "confidence": 80,
        "learned_at_tick": 0,
    }
    if _seed_edge(client, "BELIEVES", _DECEPTION_BELIEF_NPC, _DECEPTION_BELIEF_ID, edge_props) == "created":
        created += 1
    return created


def _seed_player_and_items(client: EngineClient) -> int:
    """Seed the player character, ancient_amulet item, and OWNS edge.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of nodes/edges created.
    """
    now = _now()
    created = 0

    player_payload = {
        "id": _PLAYER_ID,
        "name": "Traveler",
        "archetype": "adventurer",
        "faction": "neutral",
        "biography": "A wandering adventurer seeking fortune.",
        "is_player": True,
        "is_active": True,
        "gossipy": 50,
        "credulity": 50,
        "honesty": 60,
        "currency_balance": _PLAYER_STARTING_GOLD,
        "created_at": now,
        "updated_at": now,
        "last_graph_updated_at": now,
    }
    result = _seed_node(client, "Character", player_payload)
    if result == "created":
        created += 1

    amulet_payload = {
        "id": _AMULET_ID,
        "name": "Ancient Amulet",
        "type": "artifact",
        "description": "A heavy bronze amulet etched with unfamiliar symbols.",
        "value": 0,
        "rarity": "unique",
        "is_unique": "true",
    }
    result = _seed_node(client, "Item", amulet_payload)
    if result == "created":
        created += 1

    # Use _seed_item_edge_if_unowned so a post-delivery reseed doesn't reclaim the amulet
    result = _seed_item_edge_if_unowned(client, _PLAYER_ID, _AMULET_ID, {"acquired_at": now})
    if result == "created":
        created += 1

    return created


def _seed_aldric_inventory(client: EngineClient) -> int:
    """Seed Aldric's northern_spice_bundle Item and OWNS edge so get_sellable_items_for_npc returns it.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of nodes/edges created.
    """
    now = _now()
    created = 0
    spice_payload = {
        "id": _SPICE_ID,
        "name": "Northern Spice Bundle",
        "type": "spice",
        "value": _SPICE_VALUE,
        "rarity": "common",
        "is_unique": "false",
        "description": "A tight bundle of northern spices, rare in wartime.",
    }
    r = _seed_node(client, "Item", spice_payload)
    if r == "created":
        created += 1
    r = _seed_item_edge_if_unowned(client, "aldric_merchant", _SPICE_ID, {"acquired_at": now})
    if r == "created":
        created += 1
    return created


def _seed_aldric_currency(client: EngineClient) -> None:
    """Verify Aldric's currency_balance is set (seeded via Character payload).

    Args:
        client: Authenticated EngineClient.
    """
    existing = client.get_node("Character", "aldric_merchant")
    balance = (existing or {}).get("currency_balance", 0)
    logger.info("[seed] Aldric currency_balance=%s", balance)


def _seed_quests(client: EngineClient) -> None:
    """Seed Aldric's deliver-amulet quest deterministically, then cache quest_id.

    Creates a QuestState via POST /v1/quest/offer with a hardcoded deliver objective
    so the game can use graph-based verification. Falls back to LLM generation if
    the lifecycle route is unavailable.

    Idempotency: skips if the Quest node already exists so a completed or
    in-progress quest is not reset to "offered" on re-seed.

    Non-fatal: logs a warning and returns without raising if the quest engine
    is unavailable.

    Args:
        client: Authenticated EngineClient.
    """
    cache_path = Path(".cache/demo/aldric_quest.json")
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if client.get_node("Quest", _ALDRIC_QUEST_ID) is not None:
        logger.info("[seed] Quest %s already exists — skipped", _ALDRIC_QUEST_ID)
        return

    try:
        client.post_quest_offer(
            quest_id=_ALDRIC_QUEST_ID,
            player_id=_PLAYER_ID,
            title="Return the Ancient Amulet",
            objectives=[{
                "objective_id": "deliver_amulet",
                "target_count": 1,
                "objective_type": "deliver",
                "target_id": _AMULET_ID,
            }],
            item_rewards=[],
            currency_reward={"amount": _ALDRIC_REWARD_AMOUNT},
            reward_source_id="aldric_merchant",
        )
        cache_path.write_text(json.dumps({"quest_id": _ALDRIC_QUEST_ID}))
        logger.info("[seed] Quest offered: %s", _ALDRIC_QUEST_ID)
        # Seed Quest definition node + HAS_QUEST edge so get_offered_quests_for_npc finds it
        _seed_node(client, "Quest", {
            "id": _ALDRIC_QUEST_ID,
            "description": "Aldric wants the ancient amulet returned to him.",
            "quest_giver_id": "aldric_merchant",
            "success_condition": "player delivers ancient_amulet to aldric_merchant",
            "status": "offered",
            "severity": 30,
            "created_at": _now(),
        })
        _seed_edge(client, "HAS_QUEST", "aldric_merchant", _ALDRIC_QUEST_ID, {})
    except Exception as exc:
        logger.warning("[seed] Deterministic quest offer failed (%s) — falling back to LLM generation", exc)
        try:
            data = client.post_quest_generate("aldric_merchant")
            quest_id = data["quest_id"]
            cache_path.write_text(json.dumps({"quest_id": quest_id}))
            logger.info("[seed] Quest generated (fallback): %s", quest_id)
        except Exception as gen_exc:
            logger.warning("[seed] Quest seeding skipped: %s", gen_exc)


def _seed_source_chain_quests(client: EngineClient) -> int:
    """Seed source/trigger Quest nodes for the UNLOCKS chains (EXP-19 slice-4).

    These are the quests a player completes to trigger the chain.  Without them
    the UNLOCKS edges in _QUEST_UNLOCKS_CHAINS point from a void and no game
    interaction can ever fire the chain.

    Idempotent: skips any Quest node that already exists.
    Non-fatal: logs a warning and continues on error.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of Quest nodes created (0 if all already existed).
    """
    created = 0
    for quest in _SOURCE_CHAIN_QUESTS:
        quest_id = quest["id"]
        try:
            result = _seed_node(client, "Quest", {**quest, "created_at": _now()})
            if result == "created":
                created += 1
                logger.info("[seed] Source chain quest seeded: %s", quest_id)
            else:
                logger.info("[seed] Source chain quest %s already exists — skipped", quest_id)
            # Always seed edge: Quest may exist but edge may be missing from a partial prior run.
            _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
        except Exception as exc:
            logger.warning("[seed] Source chain quest %s skipped: %s", quest_id, exc)
    return created


def _seed_chain_quests(client: EngineClient) -> int:
    """Seed chain-target Quest nodes so QuestChainOfferAdapter can resolve them (EXP-19 slice-3).

    These Quest nodes are the successors referenced in _QUEST_UNLOCKS_CHAINS.  Without them,
    QuestChainResolver fires → get_quest returns None → QuestTransitionError at runtime.

    Idempotent: skips any Quest node that already exists.
    Non-fatal: logs a warning and continues on error.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of Quest nodes created (0 if all already existed).
    """
    created = 0
    for quest in _CHAIN_QUESTS:
        quest_id = quest["id"]
        try:
            result = _seed_node(client, "Quest", {**quest, "created_at": _now()})
            if result == "created":
                created += 1
                logger.info("[seed] Chain quest seeded: %s", quest_id)
            else:
                logger.info("[seed] Chain quest %s already exists — skipped", quest_id)
            # Always seed edge: Quest may exist but edge may be missing from a partial prior run.
            _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
        except Exception as exc:
            logger.warning("[seed] Chain quest %s skipped: %s", quest_id, exc)
    return created


def _seed_quest_unlocks_chains(client: EngineClient) -> int:
    """Seed hand-authored UNLOCKS edges between quest pairs (EXP-19 slice-1).

    These edges drive automatic quest-chain offers when the source quest
    reaches the given outcome. The upsert is idempotent — re-running seed_all
    skips any edge that already exists.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of UNLOCKS edges created (0 if all already existed).
    """
    created = 0
    for src_id, dst_id, on_outcome in _QUEST_UNLOCKS_CHAINS:
        result = _seed_edge(
            client,
            "UNLOCKS",
            src_id,
            dst_id,
            {"on_outcome": on_outcome},
        )
        if result == "created":
            created += 1
    return created


def _seed_needs(client: EngineClient) -> int:
    """Seed Need nodes, HAS_NEED edges, and SATISFIES_NEED edges for original demo NPCs.

    Creates one Need node per entry in _NPC_NEEDS, one HAS_NEED edge from the
    owning Character to each Need, and SATISFIES_NEED edges from locations to
    each Need node. Idempotent: _seed_node and _seed_edge skip items that exist.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of nodes and edges created.
    """
    created = 0
    for npc_id, kind, level, decay_rate in _NPC_NEEDS:
        node_id = f"{npc_id}_need_{kind}"
        result = _seed_node(client, "Need", {
            "id": node_id,
            "kind": kind,
            "level": level,
            "decay_rate": decay_rate,
            "character_id": npc_id,
        })
        if result == "created":
            created += 1
        result = _seed_edge(client, "HAS_NEED", npc_id, node_id, {})
        if result == "created":
            created += 1

    for loc_id, need_id, magnitude in _SATISFIES_NEED_EDGES:
        result = _seed_edge(client, "SATISFIES_NEED", loc_id, need_id, {"magnitude": magnitude})
        if result == "created":
            created += 1

    return created


def _seed_schedules(client: EngineClient) -> int:
    """Seed Schedule nodes and FOLLOWS_SCHEDULE edges for the core demo NPCs.

    Covers the three MetaHumans (mira_innkeeper, captain_sorn, lira_fence) and the
    gossip-path terminal node (old_henryk) — the minimum set routine_engine needs to
    start moving NPCs. All entries reference location IDs that already exist in the seed.

    Idempotent: _seed_node and _seed_edge skip items that already exist.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of nodes and edges created.
    """
    created = 0
    now = _now()
    for schedule_id, character_id, name, description, entries in _SCHEDULES:
        result = _seed_node(client, "Schedule", {
            "id": schedule_id,
            "name": name,
            "description": description,
            "entries": json.dumps(entries),
            "created_at": now,
            "last_graph_updated_at": now,
        })
        if result == "created":
            created += 1
        result = _seed_edge(client, "FOLLOWS_SCHEDULE", character_id, schedule_id, {})
        if result == "created":
            created += 1
    return created
