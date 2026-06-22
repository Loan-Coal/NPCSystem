"""
Module: api_seeder
Layer: data (tooling, not application code)
Purpose: World seed via the publicly-exposed HTTP API. All resources use their
         typed admin endpoints (/v1/admin/beliefs, /v1/admin/goals, etc.) rather
         than the low-level graph CRUD backdoor. Generic /v1/graph/nodes|edges/
         is only used where no typed endpoint exists (Location, Character, Event,
         and raw structural edges).
Does NOT: connect to Neo4j directly.
Dependencies: npc_engine.utils.logging (structured logging only), npc_engine.data.seed_data, npc_engine.data.seed_http.
Dependencies injected: base_url and api_key via CLI args or env vars.
Used by: make seed-api, manual tooling.

300-LINE WAIVER: data-seeding tooling — one cohesive idempotent seed flow per
resource type; a split would scatter the seed contract with no reuse value.
See DEC-140 (ISSUE-053 baseline catalog).

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

from typing import Any
import argparse
import hashlib
import os
import sys

from npc_engine.utils.logging import get_logger
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

_LOGGER = get_logger(__name__)

# Local copy of the "knows" knowledge-state value. This seeder is forbidden (per the
# module docstring) from importing application code, so it cannot reference
# npc_engine.common.knowledge_types.KNOWLEDGE_STATE_KNOWS directly — the duplication
# is deliberate (ISSUE-109).
_KNOWLEDGE_STATE_KNOWS: str = "knows"


# ---------------------------------------------------------------------------
# Stable-ID helpers (KE-6)
# ---------------------------------------------------------------------------


def _belief_id(npc_id: str, content: str) -> str:
    """Derive stable belief node ID: bel_{npc_id}_{sha1(content)[:8]}."""
    return f"bel_{npc_id}_{hashlib.sha1(content.encode()).hexdigest()[:8]}"


def _goal_id(npc_id: str, n: int) -> str:
    """Derive stable goal node ID: goal_{npc_id}_{n} (0-based index)."""
    return f"goal_{npc_id}_{n}"


def _memory_id(npc_id: str, n: int) -> str:
    """Derive stable memory node ID: mem_{npc_id}_{n} (0-based index)."""
    return f"mem_{npc_id}_{n}"


def _secret_id(npc_id: str) -> str:
    """Derive stable secret node ID: sec_{npc_id} (one secret per NPC)."""
    return f"sec_{npc_id}"


def resolve_api_key(args_key: str | None) -> str:
    """Return the API key from args or NPC_API_KEY env var; fail fast if absent.

    Args:
        args_key: Value from --api-key CLI argument (may be None or empty).

    Returns:
        Non-empty API key string.

    Raises:
        SystemExit: if neither args_key nor NPC_API_KEY is set/non-empty.
    """
    key = args_key or os.environ.get("NPC_API_KEY", "")
    if not key:
        _LOGGER.error("seeder_config_error", extra={"detail": "NPC_API_KEY env var is not set; cannot seed without a valid API key"})
        sys.exit(1)
    return key


def _seed_world_structure(base_url: str, api_key: str, now: str, c: Counter) -> None:
    """Seed Faction, Location, and Character nodes (in dependency order)."""
    _LOGGER.info("seeder_phase", extra={"phase": "factions"})
    for faction in get_factions():
        label = f"Faction:{faction['id']}"
        if faction_exists(base_url, api_key, str(faction["id"])):
            c.record(label, 409)
        else:
            status, _ = call("POST", f"{base_url}/v1/admin/factions/", api_key, faction)
            c.record(label, status)
    c.abort_if_failed()
    _LOGGER.info("seeder_phase", extra={"phase": "locations"})
    for loc in get_locations(now):
        label = f"Location:{loc['id']}"
        c.record(label, 409 if node_exists(base_url, api_key, "Location", loc["id"]) else post_node(base_url, api_key, "Location", loc))
    c.abort_if_failed()
    _LOGGER.info("seeder_phase", extra={"phase": "characters"})
    for char in get_characters(now):
        label = f"Character:{char['id']}"
        c.record(label, 409 if node_exists(base_url, api_key, "Character", char["id"]) else post_node(base_url, api_key, "Character", char))
    c.abort_if_failed()


def _seed_edges(base_url: str, api_key: str, now: str, c: Counter) -> None:
    """Seed MEMBER_OF, LOCATED_AT, and RELATES_TO structural edges."""
    _LOGGER.info("seeder_phase", extra={"phase": "MEMBER_OF edges"})
    for char_id, faction_id, role in get_faction_members():
        label = f"MEMBER_OF:{char_id}->{faction_id}"
        if edge_exists(base_url, api_key, "MEMBER_OF", char_id, faction_id):
            c.record(label, 409)
        else:
            status, _ = call("POST", f"{base_url}/v1/admin/factions/{faction_id}/members", api_key, {"character_id": char_id, "role": role, "status": "active"})
            c.record(label, status)
    c.abort_if_failed()
    _LOGGER.info("seeder_phase", extra={"phase": "LOCATED_AT edges"})
    for char_id, (loc_id, permanent) in get_character_location().items():
        label = f"LOCATED_AT:{char_id}->{loc_id}"
        if edge_exists(base_url, api_key, "LOCATED_AT", char_id, loc_id):
            c.record(label, 409)
        else:
            c.record(label, post_edge(base_url, api_key, "LOCATED_AT", char_id, loc_id, {"is_permanent_resident": permanent, "arrived_at": now}))
    c.abort_if_failed()
    _LOGGER.info("seeder_phase", extra={"phase": "RELATES_TO edges"})
    for src, dst in get_relates_to_pairs():
        label = f"RELATES_TO:{src}->{dst}"
        if edge_exists(base_url, api_key, "RELATES_TO", src, dst):
            c.record(label, 409)
        else:
            c.record(label, post_edge(base_url, api_key, "RELATES_TO", src, dst, {"trust": 50, "fear": 50, "affection": 50, "interaction_count": 0, "last_updated_at": now, "relevance_score": 0.5}))
    c.abort_if_failed()


def _seed_knows_about_edges(base_url: str, api_key: str, events: list[Any], c: Counter) -> None:
    """Seed KNOWS_ABOUT edges between all NPCs and all known events."""
    _LOGGER.info("seeder_phase", extra={"phase": "KNOWS_ABOUT edges"})
    events_by_id = {e["id"]: e for e in events}
    for npc_id in get_npc_ids():
        for evt in events:
            label = f"KNOWS_ABOUT:{npc_id}->{evt['id']}"
            if edge_exists(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"]):
                c.record(label, 409)
            else:
                props = {
                    "knowledge_state": _KNOWLEDGE_STATE_KNOWS,
                    "learned_at_tick": events_by_id[evt["id"]]["tick_id"],
                    "distortion_type": None,
                    "distortion_level": None,
                    "distorted_summary": None,
                    "source_character_id": None,
                }
                c.record(label, post_edge(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"], props))
    c.abort_if_failed()


def _seed_events(base_url: str, api_key: str, now: str, c: Counter) -> None:
    """Seed Event nodes and PARTICIPATED_IN + KNOWS_ABOUT edges."""
    events = get_events(now)
    _LOGGER.info("seeder_phase", extra={"phase": "events"})
    for evt in events:
        label = f"Event:{evt['id']}"
        c.record(label, 409 if node_exists(base_url, api_key, "Event", evt["id"]) else post_node(base_url, api_key, "Event", evt))
    c.abort_if_failed()
    _LOGGER.info("seeder_phase", extra={"phase": "PARTICIPATED_IN edges"})
    for row in get_event_participation():
        label = f"PARTICIPATED_IN:{row['character_id']}->{row['event_id']}"
        if edge_exists(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"]):
            c.record(label, 409)
        else:
            c.record(label, post_edge(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"], {"role": row["role"], "participated_at": now}))
    c.abort_if_failed()
    _seed_knows_about_edges(base_url, api_key, events, c)


def _seed_beliefs(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Belief nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "beliefs"})
    for char_id, content, confidence in get_phase3_beliefs():
        status, _ = call("POST", f"{base_url}/v1/admin/beliefs/{char_id}", api_key, {"content": content, "confidence": confidence, "game_time": game_time, "id": _belief_id(char_id, content)})
        c.record(f"Belief:{char_id}:{content[:30]}", status)
    c.abort_if_failed()


def _seed_goals(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Goal nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "goals"})
    _goal_index: dict[str, int] = {}
    for char_id, description, urgency in get_phase3_goals():
        n = _goal_index.get(char_id, 0)
        _goal_index[char_id] = n + 1
        status, _ = call("POST", f"{base_url}/v1/admin/goals/{char_id}", api_key, {"description": description, "urgency": urgency, "game_time": game_time, "id": _goal_id(char_id, n)})
        c.record(f"Goal:{char_id}:{description[:30]}", status)
    c.abort_if_failed()


def _seed_items(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Item nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "items"})
    for owner_id, name, description, value, rarity, item_type, is_unique in get_phase3_items():
        status, _ = call("POST", f"{base_url}/v1/admin/items/{owner_id}", api_key, {"name": name, "description": description, "value": value, "rarity": rarity, "type": item_type, "is_unique": is_unique, "game_time": game_time})
        c.record(f"Item:{owner_id}:{name}", status)
    c.abort_if_failed()


def _seed_secrets(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Secret nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "secrets"})
    for char_id, content, severity in get_phase3_secrets():
        status, _ = call("POST", f"{base_url}/v1/admin/secrets/{char_id}", api_key, {"content": content, "severity": severity, "game_time": game_time, "id": _secret_id(char_id)})
        c.record(f"Secret:{char_id}:{content[:30]}", status)
    c.abort_if_failed()


def _seed_memories(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Memory nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "memories"})
    _memory_index: dict[str, int] = {}
    for char_id, content, vividness, emotional_charge in get_phase3_memories():
        n = _memory_index.get(char_id, 0)
        _memory_index[char_id] = n + 1
        status, _ = call("POST", f"{base_url}/v1/admin/memories/{char_id}", api_key, {"content": content, "vividness": vividness, "emotional_charge": emotional_charge, "game_time": game_time, "id": _memory_id(char_id, n)})
        c.record(f"Memory:{char_id}:{content[:30]}", status)
    c.abort_if_failed()


def _seed_debts(base_url: str, api_key: str, game_time: dict[str, Any], c: Counter) -> None:
    """Seed Debt nodes for all characters."""
    _LOGGER.info("seeder_phase", extra={"phase": "debts"})
    for debtor_id, creditor_id, kind, magnitude, due_by in get_phase3_debts():
        status, _ = call("POST", f"{base_url}/v1/admin/debts/{debtor_id}", api_key, {"creditor_id": creditor_id, "kind": kind, "magnitude": magnitude, "due_by": due_by})
        c.record(f"Debt:{debtor_id}->{creditor_id}:{kind}", status)
    c.abort_if_failed()


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
    _seed_world_structure(base_url, api_key, now, c)
    _seed_edges(base_url, api_key, now, c)
    _seed_events(base_url, api_key, now, c)
    game_time = get_game_time()
    _seed_beliefs(base_url, api_key, game_time, c)
    _seed_goals(base_url, api_key, game_time, c)
    _seed_items(base_url, api_key, game_time, c)
    _seed_secrets(base_url, api_key, game_time, c)
    _seed_memories(base_url, api_key, game_time, c)
    _seed_debts(base_url, api_key, game_time, c)
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
        default=None,
        help="Bearer API key (env: NPC_API_KEY). Required; no default.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    api_key = resolve_api_key(args.api_key)
    _LOGGER.info("seeder_start", extra={"base_url": args.base_url})
    sys.exit(seed(base_url=args.base_url, api_key=api_key))
