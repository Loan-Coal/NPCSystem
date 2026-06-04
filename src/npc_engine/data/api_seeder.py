"""
Module: api_seeder
Layer: data (tooling, not application code)
Purpose: World seed via the publicly-exposed HTTP API. All resources use their
         typed admin endpoints (/v1/admin/beliefs, /v1/admin/goals, etc.) rather
         than the low-level graph CRUD backdoor. Generic /v1/graph/nodes|edges/
         is only used where no typed endpoint exists (Location, Character, Event,
         and raw structural edges).
Does NOT: connect to Neo4j or import any npc_engine application code.
Dependencies injected: base_url and api_key via CLI args or env vars.
Used by: make seed-api, manual tooling.

Idempotency contract (get-then-skip):
  Resources with stable IDs (Faction, Location, Character, Event, edges):
    Before each POST, a GET is issued for the stable ID.  If the resource
    already exists (HTTP 200) the creation is skipped entirely.  This makes
    the seeder safe to re-run on a populated database.

  Resources without stable IDs (Belief, Goal, Item, Secret, Memory, Debt):
    These endpoints auto-generate IDs, so there is no reliable GET-by-content
    lookup.  If the server returns HTTP 409 Conflict the call is recorded as
    skipped; all other 2xx responses are recorded as created.  Re-running on
    a populated DB will therefore still create duplicates for these resource
    types — wipe the DB if that is undesirable.
"""

from __future__ import annotations

import argparse
import sys

from npc_engine.data.seed_data import (
    get_characters,
    get_character_location,
    get_event_participation,
    get_events,
    get_faction_members,
    get_factions,
    get_game_time,
    get_locations,
    get_npc_ids,
    get_phase3_beliefs,
    get_phase3_debts,
    get_phase3_goals,
    get_phase3_items,
    get_phase3_memories,
    get_phase3_secrets,
    get_relates_to_pairs,
    now_iso,
)
from npc_engine.data.seed_http import (
    Counter,
    call,
    edge_exists,
    faction_exists,
    node_exists,
    post_edge,
    post_node,
)


def seed(base_url: str, api_key: str) -> int:
    """Seed the world via the external HTTP API.

    Args:
        base_url: API base URL, e.g. http://localhost:8000.
        api_key:  Bearer token for authentication.

    Returns:
        Exit code (0 = success, 1 = any hard failure).
    """
    c = Counter()
    now = now_iso()

    print("Seeding factions ...")
    for faction in get_factions():
        label = f"Faction:{faction['id']}"
        if faction_exists(base_url, api_key, str(faction["id"])):
            c.record(label, 409)
        else:
            status, _ = call("POST", f"{base_url}/v1/admin/factions/", api_key, faction)
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding locations ...")
    for loc in get_locations(now):
        label = f"Location:{loc['id']}"
        if node_exists(base_url, api_key, "Location", loc["id"]):
            c.record(label, 409)
        else:
            c.record(label, post_node(base_url, api_key, "Location", loc))
    c.abort_if_failed()

    print("Seeding characters ...")
    for char in get_characters(now):
        label = f"Character:{char['id']}"
        if node_exists(base_url, api_key, "Character", char["id"]):
            c.record(label, 409)
        else:
            c.record(label, post_node(base_url, api_key, "Character", char))
    c.abort_if_failed()

    print("Seeding MEMBER_OF edges ...")
    for char_id, faction_id, role in get_faction_members():
        label = f"MEMBER_OF:{char_id}->{faction_id}"
        if edge_exists(base_url, api_key, "MEMBER_OF", char_id, faction_id):
            c.record(label, 409)
        else:
            status, _ = call("POST", f"{base_url}/v1/admin/factions/{faction_id}/members", api_key, {"character_id": char_id, "role": role, "status": "active"})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding LOCATED_AT edges ...")
    for char_id, (loc_id, permanent) in get_character_location().items():
        label = f"LOCATED_AT:{char_id}->{loc_id}"
        if edge_exists(base_url, api_key, "LOCATED_AT", char_id, loc_id):
            c.record(label, 409)
        else:
            status = post_edge(base_url, api_key, "LOCATED_AT", char_id, loc_id, {"is_permanent_resident": permanent, "arrived_at": now})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding RELATES_TO edges ...")
    for src, dst in get_relates_to_pairs():
        label = f"RELATES_TO:{src}->{dst}"
        if edge_exists(base_url, api_key, "RELATES_TO", src, dst):
            c.record(label, 409)
        else:
            status = post_edge(base_url, api_key, "RELATES_TO", src, dst, {"trust": 50, "fear": 50, "affection": 50, "interaction_count": 0, "last_updated_at": now, "relevance_score": 0.5})
            c.record(label, status)
    c.abort_if_failed()

    events = get_events(now)
    print("Seeding events ...")
    for evt in events:
        label = f"Event:{evt['id']}"
        if node_exists(base_url, api_key, "Event", evt["id"]):
            c.record(label, 409)
        else:
            c.record(label, post_node(base_url, api_key, "Event", evt))
    c.abort_if_failed()

    print("Seeding PARTICIPATED_IN edges ...")
    for row in get_event_participation():
        label = f"PARTICIPATED_IN:{row['character_id']}->{row['event_id']}"
        if edge_exists(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"]):
            c.record(label, 409)
        else:
            status = post_edge(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"], {"role": row["role"], "participated_at": now})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding KNOWS_ABOUT edges ...")
    events_by_id = {e["id"]: e for e in events}
    for npc_id in get_npc_ids():
        for evt in events:
            label = f"KNOWS_ABOUT:{npc_id}->{evt['id']}"
            if edge_exists(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"]):
                c.record(label, 409)
            else:
                props = {
                    "knowledge_state": "knows",
                    "learned_at_tick": events_by_id[evt["id"]]["tick_id"],
                    "distortion_type": None,
                    "distortion_level": None,
                    "distorted_summary": None,
                    "source_character_id": None,
                }
                status = post_edge(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"], props)
                c.record(label, status)
    c.abort_if_failed()

    game_time = get_game_time()

    print("Seeding Phase 3 — Beliefs ...")
    for char_id, content, confidence in get_phase3_beliefs():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/beliefs/{char_id}",
            api_key,
            {"content": content, "confidence": confidence, "game_time": game_time},
        )
        c.record(f"Belief:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Goals ...")
    for char_id, description, urgency in get_phase3_goals():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/goals/{char_id}",
            api_key,
            {"description": description, "urgency": urgency, "game_time": game_time},
        )
        c.record(f"Goal:{char_id}:{description[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Items ...")
    for owner_id, name, description, value, rarity, item_type, is_unique in get_phase3_items():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/items/{owner_id}",
            api_key,
            {
                "name": name,
                "description": description,
                "value": value,
                "rarity": rarity,
                "type": item_type,
                "is_unique": is_unique,
                "game_time": game_time,
            },
        )
        c.record(f"Item:{owner_id}:{name}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Secrets ...")
    for char_id, content, severity in get_phase3_secrets():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/secrets/{char_id}",
            api_key,
            {"content": content, "severity": severity, "game_time": game_time},
        )
        c.record(f"Secret:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Memories ...")
    for char_id, content, vividness, emotional_charge in get_phase3_memories():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/memories/{char_id}",
            api_key,
            {
                "content": content,
                "vividness": vividness,
                "emotional_charge": emotional_charge,
                "game_time": game_time,
            },
        )
        c.record(f"Memory:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Debts ...")
    for debtor_id, creditor_id, kind, magnitude, due_by in get_phase3_debts():
        status, _ = call(
            "POST",
            f"{base_url}/v1/admin/debts/{debtor_id}",
            api_key,
            {"creditor_id": creditor_id, "kind": kind, "magnitude": magnitude, "due_by": due_by},
        )
        c.record(f"Debt:{debtor_id}->{creditor_id}:{kind}", status)
    c.abort_if_failed()

    return c.summary()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    import os
    parser = argparse.ArgumentParser(description="Seed world data via the NPC Engine HTTP API")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NPC_BASE_URL", "http://localhost:8000"),
        help="API base URL (env: NPC_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NPC_API_KEY", "local_dev_secret_change_this_2026"),
        help="Bearer API key (env: NPC_API_KEY)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(f"Seeding world at {args.base_url} ...")
    sys.exit(seed(base_url=args.base_url, api_key=args.api_key))
