"""
Module: seed
Layer: demo_game (external client)
Purpose: Orchestrate seeding of the full demo world via the NPC Engine HTTP API.
         Imports from domain sub-modules; exposes seed_all() as the entry point.
         Re-exports all public and private symbols so callers can continue to
         import from this module without change (Pre-approved: public-interface).
Dependencies: demo_game.seeds.seed_builders, demo_game.seeds.seed_io,
              demo_game.seeds.seed_world_data, demo_game.seeds.seed_domain,
              demo_game.seeds.seed_npc_data, demo_game.client (TYPE_CHECKING only)
Used by: make demo-seed, demo_game/tests/test_seed.py

See project-harness/DECISIONS.md DEC-020, DEC-021, DEC-022 for seeder conventions.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# Re-exports from sub-modules (callers may still import from this module)
# ---------------------------------------------------------------------------

from demo_game.seeds.seed_builders import (  # noqa: F401
    WorldStatePayload,
    _GAME_TIME,
    _HISTORICAL_GAME_TIME,
    _PLAYER_STARTING_GOLD,
    _WORLD_STATE_ID,
    _belief_id,
    _goal_id,
    _memory_id,
    _now,
    _secret_id,
    build_event_payload,
    build_faction_payload,
    build_location_payload,
    build_npc_payload,
    build_world_state_payload,
)
from demo_game.seeds.seed_domain import (  # noqa: F401
    _seed_aldric_currency,
    _seed_aldric_inventory,
    _seed_chain_quests,
    _seed_deception_belief,
    _seed_h2_factions,
    _seed_h2_npcs,
    _seed_h2_quests,
    _seed_location_hierarchy,
    _seed_needs,
    _seed_player_and_items,
    _seed_quest_unlocks_chains,
    _seed_quests,
    _seed_schedules,
    _seed_source_chain_quests,
)
from demo_game.seeds.seed_io import (  # noqa: F401
    _force_patch_world_state,
    _seed_edge,
    _seed_item_edge_if_unowned,
    _seed_memories,
    _seed_npc_inner_life,
    _seed_node,
)
from demo_game.seeds.seed_npc_data import (  # noqa: F401
    FACTION_ID_CROWN_LOYALISTS,
    FACTION_ID_DOCKSIDE_SMUGGLERS,
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
    H2_SOURCE_CHAIN_QUESTS,
)
from demo_game.seeds.seed_world_data import (  # noqa: F401
    _ALDRIC_QUEST_ID,
    _ALDRIC_REWARD_AMOUNT,
    _AMULET_ID,
    _ARMIES,
    _ARMY_OCCUPIES,
    _CHAIN_QUESTS,
    _DECEPTION_BELIEF_CONTENT,
    _DECEPTION_BELIEF_ID,
    _DECEPTION_BELIEF_NPC,
    _DECEPTION_GOAL_ID,
    _FACTIONS,
    _FACTION_STANDS_WITH,
    _HAS_LEVERAGE_EDGES,
    _LEVERAGE_NODES,
    _LOCATIONS,
    _MILITARY_FACTIONS,
    _NPC_INNER_LIFE,
    _NPC_LOCATED_AT,
    _NPC_MEMBER_OF,
    _NPC_NEEDS,
    _NPC_NPC_EDGES,
    _NPCS,
    _PLAYER_ID,
    _PLAYER_KNOWS_ABOUT,
    _PLEDGE_SEED,
    _QUEST_UNLOCKS_CHAINS,
    _SCHEDULES,
    _SOURCE_CHAIN_QUESTS,
    _SPICE_ID,
    _SPICE_VALUE,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------


def seed_all(client: EngineClient) -> dict:
    """Seed the full demo world via the NPC Engine HTTP API.

    Dependency order:
    1.   Locations (original + H2.3 venues)
    2.   Factions (original + iron_legion + H2.4); H2 STANDS_WITH edges
    3.   Characters (original + H2.2 NPCs with MEMBER_OF/LOCATED_AT/inner-life/Needs)
    4.   Orig NPC MEMBER_OF edges
    5.   Orig faction STANDS_WITH edges
    6.   Orig NPC inner life
    7.   Events
    8.   world_state
    9.   NPC-NPC structural edges (RELATES_TO, OPPOSES, KNOWS_ABOUT)
    10.  Orig NPC LOCATED_AT edges
    11.  Player + items + OWNS edge
    11b. Player KNOWS_ABOUT edges
    11c. Deception belief
    12.  Aldric inventory
    13.  Aldric currency check
    14.  Aldric quest (non-fatal)
    14b. Source chain quests
    14c. Chain-target quests
    15.  NPC Needs (original NPCs)
    16.  Leverage nodes + HAS_LEVERAGE edges + Pledges
    17.  Armies + OCCUPIES edges
    19.  Location hierarchy + PART_OF edges (EXP-87)
    20.  Quest UNLOCKS chains (original 2 chains)
    18.  H2.5 quests + UNLOCKS chains

    Idempotency:
    - Explicit-ID nodes: GET before POST; skip if exists.
    - Explicit-ID edges: always upsert (Neo4j MERGE).
    - Typed nodes (beliefs etc.): check BELIEVES edge count; skip NPC if any exist.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Summary dict with "created" and "skipped" integer counts.
    """
    created = 0
    skipped = 0

    def _tally(result: str) -> None:
        nonlocal created, skipped
        if result == "created":
            created += 1
        else:
            skipped += 1

    # 1. Locations (original + H2.3 new venues)
    logger.info("[seed] Locations")
    for loc_id, name, tag, descriptor in _LOCATIONS:
        _tally(_seed_node(client, "Location", build_location_payload(loc_id, name, tag, descriptor)))
    for loc_id, name, tag, descriptor in H2_LOCATIONS:
        _tally(_seed_node(client, "Location", build_location_payload(loc_id, name, tag, descriptor)))

    # 2. Factions (original + military + H2.4 new factions)
    # iron_legion must be created before _seed_h2_factions() which seeds a
    # STANDS_WITH edge from crown_loyalists → iron_legion.
    logger.info("[seed] Factions")
    for faction_id, name, archetype, description in _FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))
    for faction_id, name, archetype, description in _MILITARY_FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))
    created += _seed_h2_factions(client)

    # 3. Characters (original 8 + H2.2 6 new)
    logger.info("[seed] Characters")
    for npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor in _NPCS:
        payload = build_npc_payload(npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
        if npc_id == "aldric_merchant":
            payload["currency_balance"] = 200
        _tally(_seed_node(client, "Character", payload))
    # H2.2 new NPCs (seeded via dedicated helper to keep seed_all manageable)
    logger.info("[seed] H2 Characters + inner life + MEMBER_OF + LOCATED_AT + Needs")
    created += _seed_h2_npcs(client)

    # 4. MEMBER_OF edges
    logger.info("[seed] MEMBER_OF edges")
    for npc_id, faction_id, role in _NPC_MEMBER_OF:
        _tally(_seed_edge(client, "MEMBER_OF", npc_id, faction_id, {
            "role": role,
            "status": "active",
            "joined_at": _now(),
        }))

    # 5. Faction-faction STANDS_WITH edges (negative standing = antagonism)
    logger.info("[seed] Faction STANDS_WITH edges")
    for src_faction, dst_faction, standing in _FACTION_STANDS_WITH:
        _tally(_seed_edge(client, "STANDS_WITH", src_faction, dst_faction, {
            "standing": standing,
            "last_changed_at": "tick_0",
        }))

    # 6. NPC inner life (beliefs, goals, memories, secrets)
    logger.info("[seed] NPC inner life")
    for npc_id, life in _NPC_INNER_LIFE.items():
        n = _seed_npc_inner_life(
            client,
            npc_id,
            beliefs=life["beliefs"],
            goals=life["goals"],
            memories=life["memories"],
            secret=life["secret"],
        )
        created += n
        if n == 0:
            skipped += len(life["beliefs"]) + len(life["goals"]) + len(life["memories"]) + 1

    # 7. Events
    logger.info("[seed] Events")
    _tally(_seed_node(
        client,
        "Event",
        build_event_payload(
            id="northern_war_begins",
            summary="The northern armies have crossed the border",
            event_type="conflict",
            location_id="loc_guard_barracks",
            severity=90,
            is_public=False,
        ),
    ))
    _tally(_seed_node(
        client,
        "Event",
        build_event_payload(
            id="market_fire",
            summary="Fire breaks out in Market Square",
            event_type="disaster",
            location_id="loc_market_square",
            severity=60,
            is_public=True,
        ),
    ))

    # 8. world_state (id="world" — canonical; see DEC-022)
    logger.info("[seed] world_state")
    _tally(_seed_node(client, "world_state", build_world_state_payload("war", ["northern_war"]).model_dump()))
    _force_patch_world_state(client)  # always correct epoch even if node was skipped

    # 9. NPC-NPC structural edges
    logger.info("[seed] NPC-NPC edges")
    for edge_type, src_id, dst_id, props in _NPC_NPC_EDGES:
        _tally(_seed_edge(client, edge_type, src_id, dst_id, props))

    # 10. LOCATED_AT edges (required for gossip pair selection and game_window)
    logger.info("[seed] LOCATED_AT edges")
    for npc_id, loc_id in _NPC_LOCATED_AT:
        _tally(_seed_edge(client, "LOCATED_AT", npc_id, loc_id, {
            "is_permanent_resident": True,
            "arrived_at": _now(),
        }))

    # 11. Player character + items (ancient_amulet + HAS_ITEM edge)
    logger.info("[seed] Player + items")
    created += _seed_player_and_items(client)

    # 11b. Player KNOWS_ABOUT edges (F3.6) — after the player exists, so /player/{id}/events returns data
    logger.info("[seed] Player KNOWS_ABOUT edges")
    for event_id, props in _PLAYER_KNOWS_ABOUT:
        _tally(_seed_edge(client, "KNOWS_ABOUT", _PLAYER_ID, event_id, props))

    # 11c. Planted deception belief (G3.2) — gives the deception "tell" + intrigue arc data
    logger.info("[seed] Deception belief")
    created += _seed_deception_belief(client)

    # 12. Aldric inventory (northern_spice_bundle + OWNS edge)
    logger.info("[seed] Aldric inventory")
    created += _seed_aldric_inventory(client)

    # 13. Aldric currency balance (ensure NPC purse covers quest reward)
    logger.info("[seed] Aldric currency")
    _seed_aldric_currency(client)

    # 14. Quests (non-fatal — requires quest engine)
    logger.info("[seed] Quests")
    _seed_quests(client)

    # 14b. Source chain Quest nodes (EXP-19 slice-4) — trigger quests players complete to fire chains
    logger.info("[seed] Source chain quests")
    created += _seed_source_chain_quests(client)

    # 14c. Chain-target Quest nodes (EXP-19 slice-3) — must exist before UNLOCKS edges (step 13/end)
    logger.info("[seed] Chain quests")
    created += _seed_chain_quests(client)

    # 15. NPC Needs (original NPCs): Need nodes + HAS_NEED + SATISFIES_NEED edges
    logger.info("[seed] NPC Needs")
    created += _seed_needs(client)

    # 16. Political layer — Leverage nodes + HAS_LEVERAGE edges + Pledges
    logger.info("[seed] Leverage nodes")
    for lv_id, demand, status, created_at_tick in _LEVERAGE_NODES:
        _tally(_seed_node(client, "Leverage", {
            "id": lv_id,
            "demand": demand,
            "status": status,
            "created_at_tick": created_at_tick,
        }))

    logger.info("[seed] HAS_LEVERAGE edges")
    for holder_id, lv_id in _HAS_LEVERAGE_EDGES:
        _tally(_seed_edge(client, "HAS_LEVERAGE", holder_id, lv_id, {}))

    logger.info("[seed] Pledges")
    for pledger_id, pledgee_id, pledge_type, tick in _PLEDGE_SEED:
        try:
            existing = client.get_pledges_for_npc(pledger_id)
            already_exists = any(
                p.get("pledgee_id") == pledgee_id and p.get("pledge_type") == pledge_type
                for p in existing
            )
            if already_exists:
                skipped += 1
                continue
            client.post_pledge(pledger_id, pledgee_id, pledge_type, tick)
            created += 1
        except Exception as exc:
            logger.warning("[seed] Pledge %s→%s skipped: %s", pledger_id, pledgee_id, exc)
            skipped += 1

    # 17. Military layer — armies + OCCUPIES edges (iron_legion faction seeded at step 2)
    logger.info("[seed] Armies")
    for army_id, faction_id, strength, location_id, composition in _ARMIES:
        _tally(_seed_node(client, "Army", {
            "id": army_id,
            "faction_id": faction_id,
            "strength": strength,
            "current_location_id": location_id,
            "composition": composition,
        }))

    logger.info("[seed] OCCUPIES edges")
    for army_id, location_id, since_tick in _ARMY_OCCUPIES:
        _tally(_seed_edge(client, "OCCUPIES", army_id, location_id, {"since_tick": since_tick}))

    # 19. Location hierarchy (EXP-87)
    logger.info("[seed] Location hierarchy")
    hierarchy_created = _seed_location_hierarchy(client)
    created += hierarchy_created

    # 20. Quest UNLOCKS chains (EXP-19, original 2 chains)
    logger.info("[seed] Quest UNLOCKS chains")
    created += _seed_quest_unlocks_chains(client)

    # 18. H2.5: 12 new quests across 6 new chains
    logger.info("[seed] H2 quests + chains")
    created += _seed_h2_quests(client)

    # 21. Schedules (T5.1) — after all Characters and Locations exist
    logger.info("[seed] Schedules + FOLLOWS_SCHEDULE edges")
    created += _seed_schedules(client)

    logger.info("[seed] Done — created=%d skipped=%d", created, skipped)
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from demo_game.client import EngineClient
    from demo_game.config import get_demo_config

    base_url = os.environ.get("NPC_BASE_URL", get_demo_config().NPC_BASE_URL)
    api_key = os.environ.get("NPC_API_KEY", get_demo_config().NPC_API_KEY)

    client = EngineClient(base_url, api_key)
    try:
        result = seed_all(client)
        print(f"Seed complete — created={result['created']} skipped={result['skipped']}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
