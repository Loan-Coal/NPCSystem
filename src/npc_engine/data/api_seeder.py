"""
Module: api_seeder
Layer: data (tooling, not application code)
Purpose: Idempotent world seed via HTTP API. Mirrors the old seed.py but
         targets the external API instead of Neo4j directly. Designed to run
         from outside the Docker artifact, mimicking client behaviour.
Does NOT: connect to Neo4j or import any npc_engine application code.
         WorldState node seeding is skipped (created lazily by the game engine).
Dependencies injected: base_url and api_key via CLI args or env vars.
Used by: make seed-api, manual tooling.
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

def _locations(now: str) -> list[dict]:
    """Return location property dicts with a consistent timestamp."""
    return [
        {"id": "loc_tavern", "name": "Iron Lantern", "region": "North", "location_tag": "tavern", "descriptor": "A busy tavern.", "last_graph_updated_at": now},
        {"id": "loc_market", "name": "Grand Market", "region": "Central", "location_tag": "market", "descriptor": "Crowded stalls.", "last_graph_updated_at": now},
        {"id": "loc_keep", "name": "Stone Keep", "region": "Central", "location_tag": "keep", "descriptor": "Fortified keep.", "last_graph_updated_at": now},
        {"id": "loc_docks", "name": "Salt Docks", "region": "South", "location_tag": "docks", "descriptor": "Trading harbor.", "last_graph_updated_at": now},
        {"id": "loc_temple", "name": "Sun Temple", "region": "East", "location_tag": "temple", "descriptor": "Quiet sanctuary.", "last_graph_updated_at": now},
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
# Phase 3 seed data (deterministic IDs for idempotency)
# ---------------------------------------------------------------------------

_GAME_TIME_JSON = '{"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}'

# (id, character_id, content, confidence)
_PHASE3_BELIEFS: list[tuple[str, str, str, int]] = [
    ("seed_belief_npc1_001", "npc_1", "The guild will betray the city if it profits them.", 80),
    ("seed_belief_npc1_002", "npc_1", "Temple priests preach peace but hoard wealth.", 55),
    ("seed_belief_npc2_001", "npc_2", "The guards are all in the guild's pocket.", 90),
    ("seed_belief_npc2_002", "npc_2", "A stranger in town means trouble.", 40),
    ("seed_belief_npc3_001", "npc_3", "The docks have always been dangerous at night.", 70),
    ("seed_belief_npc4_001", "npc_4", "A deal made over ale is more binding than paper.", 65),
]

# (id, character_id, description, urgency)
_PHASE3_GOALS: list[tuple[str, str, str, int]] = [
    ("seed_goal_npc1_001", "npc_1", "Expose the guild's corruption to the city council.", 75),
    ("seed_goal_npc2_001", "npc_2", "Gather enough coin to leave this town.", 60),
    ("seed_goal_npc3_001", "npc_3", "Find out what happened to the missing shipment.", 85),
    ("seed_goal_npc4_001", "npc_4", "Win the respect of the guild officers.", 40),
]

# (id, owner_id, name, description, value, rarity, item_type, is_unique)
_PHASE3_ITEMS: list[tuple[str, str, str, str, int, str, str, str]] = [
    ("seed_item_001", "npc_1", "Guild Ledger", "Detailed record of guild transactions.", 500, "rare", "document", "true"),
    ("seed_item_002", "npc_3", "Smuggler's Compass", "Points toward nearby contraband.", 150, "uncommon", "tool", "false"),
    ("seed_item_003", "npc_4", "Silver Dagger", "A foreman's sidearm.", 80, "common", "weapon", "false"),
]

# (id, character_id, content, severity)
_PHASE3_SECRETS: list[tuple[str, str, str, int]] = [
    ("seed_secret_npc1_001", "npc_1", "The guild master paid off the city treasurer last winter.", 80),
    ("seed_secret_npc2_001", "npc_2", "There is a secret tunnel from the tavern to the docks.", 60),
]

# (id, character_id, content, vividness, emotional_charge)
_PHASE3_MEMORIES: list[tuple[str, str, str, int, int]] = [
    ("seed_mem_npc1_001", "npc_1", "The night the guild burned the merchant's warehouse. I watched from across the street.", 85, 70),
    ("seed_mem_npc2_001", "npc_2", "The day I arrived in this town with nothing but a satchel and a lie.", 90, -60),
]

# (debtor_id, creditor_id, kind, magnitude, due_by, status)
_PHASE3_DEBTS: list[tuple[str, str, str, str, str, str]] = [
    ("npc_1", "npc_2", "favor", "Promised to speak on Sera's behalf to the guild.", "Year 1 Spring Day 10", "pending"),
    ("npc_3", "npc_4", "money", "50 gold for dock fees paid in advance.", "Year 1 Spring Day 15", "pending"),
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

    print("Seeding locations ...")
    for loc in _locations(now):
        c.record(f"Location:{loc['id']}", _post_node(base_url, api_key, "Location", loc))
    c.abort_if_failed()

    print("Seeding characters ...")
    for char in _characters(now):
        c.record(f"Character:{char['id']}", _post_node(base_url, api_key, "Character", char))
    c.abort_if_failed()

    print("Seeding LOCATED_AT edges ...")
    for char_id, (loc_id, permanent) in _CHARACTER_LOCATION.items():
        status = _post_edge(base_url, api_key, "LOCATED_AT", char_id, loc_id, {"is_permanent_resident": permanent, "arrived_at": now})
        c.record(f"LOCATED_AT:{char_id}->{loc_id}", status)
    c.abort_if_failed()

    print("Seeding RELATES_TO edges ...")
    for src, dst in _RELATES_TO_PAIRS:
        status = _post_edge(base_url, api_key, "RELATES_TO", src, dst, {"trust": 50, "fear": 50, "affection": 50, "interaction_count": 0, "last_updated_at": now, "relevance_score": 0.5})
        c.record(f"RELATES_TO:{src}->{dst}", status)
    c.abort_if_failed()

    events = _events(now)
    print("Seeding events ...")
    for evt in events:
        c.record(f"Event:{evt['id']}", _post_node(base_url, api_key, "Event", evt))
    c.abort_if_failed()

    print("Seeding PARTICIPATED_IN edges ...")
    for row in _EVENT_PARTICIPATION:
        status = _post_edge(base_url, api_key, "PARTICIPATED_IN", row["character_id"], row["event_id"], {"role": row["role"], "participated_at": now})
        c.record(f"PARTICIPATED_IN:{row['character_id']}->{row['event_id']}", status)
    c.abort_if_failed()

    print("Seeding KNOWS_ABOUT edges ...")
    events_by_id = {e["id"]: e for e in events}
    for npc_id in _NPC_IDS:
        for evt in events:
            props = {
                "knowledge_state": "knows",
                "learned_at_tick": events_by_id[evt["id"]]["tick_id"],
                "distortion_type": None,
                "distortion_level": None,
                "distorted_summary": None,
                "source_character_id": None,
            }
            status = _post_edge(base_url, api_key, "KNOWS_ABOUT", npc_id, evt["id"], props)
            c.record(f"KNOWS_ABOUT:{npc_id}->{evt['id']}", status)
    c.abort_if_failed()

    print("Seeding Phase 3 — Beliefs ...")
    for belief_id, char_id, content, confidence in _PHASE3_BELIEFS:
        props = {
            "id": belief_id,
            "content": content,
            "confidence": confidence,
            "created_at_game_time": _GAME_TIME_JSON,
        }
        c.record(f"Belief:{belief_id}", _post_node(base_url, api_key, "Belief", props))
        c.record(f"BELIEVES:{char_id}->{belief_id}", _post_edge(base_url, api_key, "BELIEVES", char_id, belief_id))
    c.abort_if_failed()

    print("Seeding Phase 3 — Goals ...")
    for goal_id, char_id, description, urgency in _PHASE3_GOALS:
        props = {
            "id": goal_id,
            "description": description,
            "urgency": urgency,
            "status": "active",
            "created_at_game_time": _GAME_TIME_JSON,
        }
        c.record(f"Goal:{goal_id}", _post_node(base_url, api_key, "Goal", props))
        c.record(f"PURSUES:{char_id}->{goal_id}", _post_edge(base_url, api_key, "PURSUES", char_id, goal_id))
    c.abort_if_failed()

    print("Seeding Phase 3 — Items ...")
    for item_id, owner_id, name, description, value, rarity, item_type, is_unique in _PHASE3_ITEMS:
        props = {
            "id": item_id,
            "name": name,
            "description": description,
            "value": value,
            "rarity": rarity,
            "type": item_type,
            "is_unique": is_unique,
        }
        c.record(f"Item:{item_id}", _post_node(base_url, api_key, "Item", props))
        c.record(
            f"OWNS:{owner_id}->{item_id}",
            _post_edge(base_url, api_key, "OWNS", owner_id, item_id, {"acquired_at": _GAME_TIME_JSON}),
        )
    c.abort_if_failed()

    print("Seeding Phase 3 — Secrets ...")
    for secret_id, char_id, content, severity in _PHASE3_SECRETS:
        props = {
            "id": secret_id,
            "content": content,
            "severity": severity,
            "created_at": _GAME_TIME_JSON,
        }
        c.record(f"Secret:{secret_id}", _post_node(base_url, api_key, "Secret", props))
        c.record(
            f"KNOWS_SECRET:{char_id}->{secret_id}",
            _post_edge(base_url, api_key, "KNOWS_SECRET", char_id, secret_id, {"knowledge_state": "knows"}),
        )
    c.abort_if_failed()

    print("Seeding Phase 3 — Memories ...")
    for mem_id, char_id, content, vividness, emotional_charge in _PHASE3_MEMORIES:
        props = {
            "id": mem_id,
            "content": content,
            "vividness": vividness,
            "emotional_charge": emotional_charge,
            "created_at_game_time": _GAME_TIME_JSON,
            "last_recalled_at": _GAME_TIME_JSON,
        }
        c.record(f"Memory:{mem_id}", _post_node(base_url, api_key, "Memory", props))
        c.record(
            f"REMEMBERS:{char_id}->{mem_id}",
            _post_edge(base_url, api_key, "REMEMBERS", char_id, mem_id, {"since_game_time": _GAME_TIME_JSON}),
        )
    c.abort_if_failed()

    print("Seeding Phase 3 — Debts ...")
    for debtor_id, creditor_id, kind, magnitude, due_by, status in _PHASE3_DEBTS:
        edge_props = {
            "kind": kind,
            "magnitude": magnitude,
            "due_by": due_by,
            "status": status,
        }
        label = f"OWES:{debtor_id}->{creditor_id}:{kind}"
        c.record(label, _post_edge(base_url, api_key, "OWES", debtor_id, creditor_id, edge_props))
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
