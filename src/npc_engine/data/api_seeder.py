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
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Seed data constants
# ---------------------------------------------------------------------------

_FACTIONS = [
    {"id": "guild", "name": "Merchant Guild", "archetype": "mercantile", "description": "The powerful trade guild that controls commerce in the city.", "is_active": True},
    {"id": "guard", "name": "City Guard", "archetype": "military", "description": "The city's law enforcement and defensive force.", "is_active": True},
    {"id": "temple", "name": "Temple Order", "archetype": "religious", "description": "The religious order that runs the city's temples.", "is_active": True},
    {"id": "dockers", "name": "Dockworkers Union", "archetype": "social", "description": "The union representing dockworkers and sailors.", "is_active": True},
    {"id": "free", "name": "Free Folk", "archetype": "other", "description": "Independent citizens with no faction allegiance.", "is_active": True},
]

# (character_id, faction_id, role)
_FACTION_MEMBERS = [
    ("npc_1", "guild", "officer"),
    ("npc_6", "guild", "member"),
    ("npc_2", "guard", "officer"),
    ("npc_8", "guard", "member"),
    ("guard_1", "guard", "member"),
    ("npc_3", "temple", "officer"),
    ("npc_9", "temple", "member"),
    ("npc_4", "dockers", "officer"),
    ("npc_10", "dockers", "member"),
]


def _locations(now: str) -> list[dict]:
    """Return location property dicts with a consistent timestamp."""
    return [
        {"id": "loc_tavern", "name": "Iron Lantern", "region": "North", "location_tag": "tavern", "descriptor": "A busy tavern.", "last_graph_updated_at": now},
        {"id": "loc_market", "name": "Grand Market", "region": "Central", "location_tag": "market", "descriptor": "Crowded stalls.", "last_graph_updated_at": now},
        {"id": "loc_keep", "name": "Stone Keep", "region": "Central", "location_tag": "keep", "descriptor": "Fortified keep.", "last_graph_updated_at": now},
        {"id": "loc_docks", "name": "Salt Docks", "region": "South", "location_tag": "docks", "descriptor": "Trading harbor.", "last_graph_updated_at": now},
        {"id": "loc_temple", "name": "Sun Temple", "region": "East", "location_tag": "temple", "descriptor": "Quiet sanctuary.", "last_graph_updated_at": now},
        {"id": "loc_gate", "name": "City Gate", "region": "North", "location_tag": "gate", "descriptor": "The northern gate checkpoint.", "last_graph_updated_at": now},
    ]

_CHARACTER_LOCATION: dict[str, tuple[str, bool]] = {
    # id -> (location_id, is_permanent_resident)
    "player_1":  ("loc_market",  False),
    "npc_1":     ("loc_market",  True),
    "npc_2":     ("loc_keep",    True),
    "npc_3":     ("loc_temple",  True),
    "npc_4":     ("loc_docks",   True),
    "npc_5":     ("loc_tavern",  True),
    "npc_6":     ("loc_market",  True),
    "npc_7":     ("loc_market",  True),
    "npc_8":     ("loc_keep",    True),
    "npc_9":     ("loc_temple",  True),
    "npc_10":    ("loc_docks",   True),
    "npc_11":    ("loc_tavern",  True),
    "guard_1":   ("loc_gate",   True),
}

_RELATES_TO_PAIRS: list[tuple[str, str]] = [
    # Same location: market
    ("npc_1", "npc_6"), ("npc_6", "npc_1"),
    ("npc_1", "npc_7"), ("npc_7", "npc_1"),
    ("npc_6", "npc_7"), ("npc_7", "npc_6"),
    # Same location: keep
    ("npc_2", "npc_8"), ("npc_8", "npc_2"),
    # Same location: temple
    ("npc_3", "npc_9"), ("npc_9", "npc_3"),
    # Same location: docks
    ("npc_4", "npc_10"), ("npc_10", "npc_4"),
    # Same location: tavern
    ("npc_5", "npc_11"), ("npc_11", "npc_5"),
    # Same faction (free), different location: tavern ↔ market
    ("npc_5", "npc_7"), ("npc_7", "npc_5"),
    ("npc_7", "npc_11"), ("npc_11", "npc_7"),
]

_EVENT_PARTICIPATION: list[dict[str, str]] = [
    {"character_id": "npc_1",  "event_id": "event_1", "role": "witness"},
    {"character_id": "npc_7",  "event_id": "event_1", "role": "witness"},
    {"character_id": "npc_2",  "event_id": "event_2", "role": "witness"},
    {"character_id": "npc_8",  "event_id": "event_2", "role": "witness"},
    {"character_id": "npc_3",  "event_id": "event_3", "role": "witness"},
    {"character_id": "npc_9",  "event_id": "event_3", "role": "witness"},
]

_NPC_IDS: list[str] = [f"npc_{i}" for i in range(1, 12)]

# ---------------------------------------------------------------------------
# Phase 3 seed data
# IDs are auto-generated by the typed admin endpoints. Re-seeding on a
# populated DB will create duplicates; wipe first if that matters.
# ---------------------------------------------------------------------------

_GAME_TIME = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}

# (character_id, content, confidence)
_PHASE3_BELIEFS: list[tuple[str, str, int]] = [
    ("npc_1", "The guild will betray the city if it profits them.", 80),
    ("npc_1", "Temple priests preach peace but hoard wealth.", 55),
    ("npc_2", "The guards are all in the guild's pocket.", 90),
    ("npc_2", "A stranger in town means trouble.", 40),
    ("npc_3", "The docks have always been dangerous at night.", 70),
    ("npc_4", "A deal made over ale is more binding than paper.", 65),
]

# (character_id, description, urgency)
_PHASE3_GOALS: list[tuple[str, str, int]] = [
    ("npc_1", "Expose the guild's corruption to the city council.", 75),
    ("npc_2", "Gather enough coin to leave this town.", 60),
    ("npc_3", "Find out what happened to the missing shipment.", 85),
    ("npc_4", "Win the respect of the guild officers.", 40),
]

# (owner_id, name, description, value, rarity, item_type, is_unique)
_PHASE3_ITEMS: list[tuple[str, str, str, int, str, str, bool]] = [
    ("npc_1", "Guild Ledger", "Detailed record of guild transactions.", 500, "rare", "document", True),
    ("npc_3", "Smuggler's Compass", "Points toward nearby contraband.", 150, "uncommon", "tool", False),
    ("npc_4", "Silver Dagger", "A foreman's sidearm.", 80, "common", "weapon", False),
]

# (character_id, content, severity)
_PHASE3_SECRETS: list[tuple[str, str, int]] = [
    ("npc_1", "The guild master paid off the city treasurer last winter.", 80),
    ("npc_2", "There is a secret tunnel from the tavern to the docks.", 60),
]

# (character_id, content, vividness, emotional_charge)
_PHASE3_MEMORIES: list[tuple[str, str, int, int]] = [
    ("npc_1", "The night the guild burned the merchant's warehouse. I watched from across the street.", 85, 70),
    ("npc_2", "The day I arrived in this town with nothing but a satchel and a lie.", 90, -60),
]

# (debtor_id, creditor_id, kind, magnitude, due_by)
_PHASE3_DEBTS: list[tuple[str, str, str, str, str]] = [
    ("npc_1", "npc_2", "favor", "Promised to speak on Sera's behalf to the guild.", "Year 1 Spring Day 10"),
    ("npc_3", "npc_4", "money", "50 gold for dock fees paid in advance.", "Year 1 Spring Day 15"),
]


def _characters(now: str) -> list[dict]:
    """Return character property dicts with a consistent timestamp."""
    return [
        {"id": "player_1", "name": "Player", "archetype": "adventurer", "faction": "free", "biography": "A wandering player.", "is_player": True, "is_active": False, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 50, "credulity": 50, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_1", "name": "Aldric", "archetype": "merchant", "faction": "guild", "biography": "Veteran merchant.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 70, "credulity": 45, "honesty": 65, "current_mood": "neutral"},
        {"id": "npc_2", "name": "Sera", "archetype": "guard", "faction": "guard", "biography": "City guard captain.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 30, "credulity": 35, "honesty": 80, "current_mood": "neutral"},
        {"id": "npc_3", "name": "Mira", "archetype": "healer", "faction": "temple", "biography": "Temple healer.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 45, "credulity": 65, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_4", "name": "Garr", "archetype": "sailor", "faction": "dockers", "biography": "Dock foreman.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 80, "credulity": 55, "honesty": 40, "current_mood": "neutral"},
        {"id": "npc_5", "name": "Lenna", "archetype": "barkeep", "faction": "free", "biography": "Runs the tavern.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 85, "credulity": 50, "honesty": 55, "current_mood": "neutral"},
        {"id": "npc_6", "name": "Ivor", "archetype": "scribe", "faction": "guild", "biography": "Guild record keeper.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 35, "credulity": 40, "honesty": 70, "current_mood": "neutral"},
        {"id": "npc_7", "name": "Rook", "archetype": "thief", "faction": "free", "biography": "Streetwise pickpocket.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 90, "credulity": 45, "honesty": 25, "current_mood": "neutral"},
        {"id": "npc_8", "name": "Bran", "archetype": "guard", "faction": "guard", "biography": "Gate sentry.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 25, "credulity": 40, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_9", "name": "Thalia", "archetype": "acolyte", "faction": "temple", "biography": "Young acolyte.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 50, "credulity": 75, "honesty": 60, "current_mood": "neutral"},
        {"id": "npc_10", "name": "Dorn", "archetype": "fisher", "faction": "dockers", "biography": "Harbor fisher.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 60, "credulity": 60, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_11", "name": "Edda", "archetype": "bard", "faction": "free", "biography": "Traveling bard.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 88, "credulity": 42, "honesty": 52, "current_mood": "neutral"},
        {"id": "guard_1", "name": "Halvard", "archetype": "guard", "faction": "guard", "biography": "Veteran gate guard who has watched the north road for fifteen years.", "is_player": False, "is_active": True, "created_at": now, "updated_at": now, "last_graph_updated_at": now, "gossipy": 20, "credulity": 35, "honesty": 85, "current_mood": "neutral"},
    ]


def _events(now: str) -> list[dict]:
    """Return event property dicts with a current timestamp."""
    return [
        {"id": "event_1", "summary": "A fire damaged the south warehouse.", "severity": 70, "location_id": "loc_market", "occurred_at": now, "tick_id": 1, "event_type": "crime", "is_public": True, "last_graph_updated_at": now},
        {"id": "event_2", "summary": "Bandits clashed with guards at the north gate.", "severity": 60, "location_id": "loc_keep", "occurred_at": now, "tick_id": 2, "event_type": "battle", "is_public": True, "last_graph_updated_at": now},
        {"id": "event_3", "summary": "A rare relic was discovered near the temple.", "severity": 50, "location_id": "loc_temple", "occurred_at": now, "tick_id": 3, "event_type": "discovery", "is_public": True, "last_graph_updated_at": now},
    ]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


@dataclass
class _Counter:
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)

    def record(self, label: str, status: int) -> None:
        """Record an API call result and print one line of output."""
        if 200 <= status < 300:
            self.ok += 1
            print(f"  [OK]   {label}")
        elif status == 409:
            self.skipped += 1
            print(f"  [SKIP] {label} (already exists)")
        else:
            self.failed += 1
            self.failures.append(f"{label} (HTTP {status})")
            print(f"  [FAIL] {label} (HTTP {status})")

    def abort_if_failed(self) -> None:
        """Raise SystemExit when any hard failure has occurred."""
        if self.failed:
            print(f"\nAborting: {self.failed} failure(s): {self.failures}")
            sys.exit(1)

    def summary(self) -> int:
        """Print totals and return exit code."""
        total = self.ok + self.skipped + self.failed
        print(f"\n{self.ok} created, {self.skipped} skipped, {self.failed} failed / {total} total")
        return 1 if self.failed else 0


def _call(method: str, url: str, api_key: str, body: dict | None = None) -> tuple[int, Any]:
    """Execute an HTTP request and return (status_code, parsed_body)."""
    data = json.dumps(body).encode() if body is not None else None
    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {}


def _post_node(base: str, api_key: str, node_type: str, props: dict) -> int:
    """POST a node upsert; returns HTTP status."""
    status, _ = _call("POST", f"{base}/v1/graph/nodes/{node_type}", api_key, {"properties": props})
    return status


def _post_edge(base: str, api_key: str, edge_type: str, src: str, dst: str, props: dict | None = None) -> int:
    """POST an edge upsert; returns HTTP status."""
    body: dict[str, Any] = {"src_id": src, "dst_id": dst, "properties": props or {}}
    status, _ = _call("POST", f"{base}/v1/graph/edges/{edge_type}", api_key, body)
    return status


def _node_exists(base: str, api_key: str, node_type: str, node_id: str) -> bool:
    """Return True when a node with the given type and stable id already exists.

    Uses GET /v1/graph/nodes/{node_type}/{node_id}.  Any non-200 response
    (including 404) is treated as "does not exist".
    """
    status, _ = _call("GET", f"{base}/v1/graph/nodes/{node_type}/{node_id}", api_key)
    return status == 200


def _faction_exists(base: str, api_key: str, faction_id: str) -> bool:
    """Return True when the faction with the given stable id already exists.

    Uses GET /v1/admin/factions/{faction_id}.  Any non-200 response is treated
    as "does not exist".
    """
    status, _ = _call("GET", f"{base}/v1/admin/factions/{faction_id}", api_key)
    return status == 200


def _edge_exists(base: str, api_key: str, edge_type: str, src: str, dst: str) -> bool:
    """Return True when the directed edge between src and dst already exists.

    Uses GET /v1/graph/edges/{edge_type}?src_id={src}&dst_id={dst}.  Any
    non-200 response is treated as "does not exist".
    """
    url = f"{base}/v1/graph/edges/{edge_type}?src_id={src}&dst_id={dst}"
    status, _ = _call("GET", url, api_key)
    return status == 200


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed(base_url: str, api_key: str) -> int:
    """Seed the world via the external HTTP API.

    Args:
        base_url: API base URL, e.g. http://localhost:8000.
        api_key:  Bearer token for authentication.

    Returns:
        Exit code (0 = success, 1 = any hard failure).
    """
    c = _Counter()
    now = datetime.now(timezone.utc).isoformat()

    print("Seeding factions ...")
    for faction in _FACTIONS:
        label = f"Faction:{faction['id']}"
        if _faction_exists(base_url, api_key, faction["id"]):
            c.record(label, 409)
        else:
            status, _ = _call("POST", f"{base_url}/v1/admin/factions/", api_key, faction)
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding locations ...")
    for loc in _locations(now):
        label = f"Location:{loc['id']}"
        if _node_exists(base_url, api_key, "Location", loc["id"]):
            c.record(label, 409)
        else:
            c.record(label, _post_node(base_url, api_key, "Location", loc))
    c.abort_if_failed()

    print("Seeding characters ...")
    for char in _characters(now):
        label = f"Character:{char['id']}"
        if _node_exists(base_url, api_key, "Character", char["id"]):
            c.record(label, 409)
        else:
            c.record(label, _post_node(base_url, api_key, "Character", char))
    c.abort_if_failed()

    print("Seeding MEMBER_OF edges ...")
    for char_id, faction_id, role in _FACTION_MEMBERS:
        label = f"MEMBER_OF:{char_id}->{faction_id}"
        if _edge_exists(base_url, api_key, "MEMBER_OF", char_id, faction_id):
            c.record(label, 409)
        else:
            status, _ = _call("POST", f"{base_url}/v1/admin/factions/{faction_id}/members", api_key, {"character_id": char_id, "role": role, "status": "active"})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding LOCATED_AT edges ...")
    for char_id, (loc_id, permanent) in _CHARACTER_LOCATION.items():
        label = f"LOCATED_AT:{char_id}->{loc_id}"
        if _edge_exists(base_url, api_key, "LOCATED_AT", char_id, loc_id):
            c.record(label, 409)
        else:
            status = _post_edge(base_url, api_key, "LOCATED_AT", char_id, loc_id, {"is_permanent_resident": permanent, "arrived_at": now})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding RELATES_TO edges ...")
    for src, dst in _RELATES_TO_PAIRS:
        label = f"RELATES_TO:{src}->{dst}"
        if _edge_exists(base_url, api_key, "RELATES_TO", src, dst):
            c.record(label, 409)
        else:
            status = _post_edge(base_url, api_key, "RELATES_TO", src, dst, {"trust": 50, "fear": 50, "affection": 50, "interaction_count": 0, "last_updated_at": now, "relevance_score": 0.5})
            c.record(label, status)
    c.abort_if_failed()

    events = _events(now)
    print("Seeding events ...")
    for evt in events:
        label = f"Event:{evt['id']}"
        if _node_exists(base_url, api_key, "Event", evt["id"]):
            c.record(label, 409)
        else:
            c.record(label, _post_node(base_url, api_key, "Event", evt))
    c.abort_if_failed()

    print("Seeding PARTICIPATED_IN edges ...")
    for row in _EVENT_PARTICIPATION:
        label = f"PARTICIPATED_IN:{row['character_id']}->{row['event_id']}"
        if _edge_exists(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"]):
            c.record(label, 409)
        else:
            status = _post_edge(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"], {"role": row["role"], "participated_at": now})
            c.record(label, status)
    c.abort_if_failed()

    print("Seeding KNOWS_ABOUT edges ...")
    events_by_id = {e["id"]: e for e in events}
    for npc_id in _NPC_IDS:
        for evt in events:
            label = f"KNOWS_ABOUT:{npc_id}->{evt['id']}"
            if _edge_exists(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"]):
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
                status = _post_edge(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"], props)
                c.record(label, status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Beliefs ...")
    for char_id, content, confidence in _PHASE3_BELIEFS:
        status, _ = _call(
            "POST",
            f"{base_url}/v1/admin/beliefs/{char_id}",
            api_key,
            {"content": content, "confidence": confidence, "game_time": _GAME_TIME},
        )
        c.record(f"Belief:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Goals ...")
    for char_id, description, urgency in _PHASE3_GOALS:
        status, _ = _call(
            "POST",
            f"{base_url}/v1/admin/goals/{char_id}",
            api_key,
            {"description": description, "urgency": urgency, "game_time": _GAME_TIME},
        )
        c.record(f"Goal:{char_id}:{description[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Items ...")
    for owner_id, name, description, value, rarity, item_type, is_unique in _PHASE3_ITEMS:
        status, _ = _call(
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
                "game_time": _GAME_TIME,
            },
        )
        c.record(f"Item:{owner_id}:{name}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Secrets ...")
    for char_id, content, severity in _PHASE3_SECRETS:
        status, _ = _call(
            "POST",
            f"{base_url}/v1/admin/secrets/{char_id}",
            api_key,
            {"content": content, "severity": severity, "game_time": _GAME_TIME},
        )
        c.record(f"Secret:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Memories ...")
    for char_id, content, vividness, emotional_charge in _PHASE3_MEMORIES:
        status, _ = _call(
            "POST",
            f"{base_url}/v1/admin/memories/{char_id}",
            api_key,
            {
                "content": content,
                "vividness": vividness,
                "emotional_charge": emotional_charge,
                "game_time": _GAME_TIME,
            },
        )
        c.record(f"Memory:{char_id}:{content[:30]}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Debts ...")
    for debtor_id, creditor_id, kind, magnitude, due_by in _PHASE3_DEBTS:
        status, _ = _call(
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
