"""
Module: seed_tavern_world
Layer: seeds/worlds (external client)
Purpose: Seed the tavern eval world via the NPC Engine HTTP API. Idempotent on re-run.
Dependencies: demo_game.client
Used by: make seed-tavern-world, python seeds/worlds/seed_tavern_world.py

World prefix: tw_
World theme: inn, market, travelling merchants — no war or military context.
Intended use: eval cases that require independent non-demo NPCs (tw_innkeeper,
tw_wanderer, tw_merchant) and civilian events (theft, fire, performer).

Run from repo root so demo_game is importable:
    python seeds/worlds/seed_tavern_world.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import hashlib
import logging
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)

_GAME_TIME: dict = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}


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


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def build_location_payload(
    id: str,
    name: str,
    location_tag: str,
    descriptor: str,
) -> dict:
    """Return a Location node property dict ready for upsert_node."""
    now = _now()
    return {
        "id": id,
        "name": name,
        "location_tag": location_tag,
        "descriptor": descriptor,
        "region": "town",
        "last_graph_updated_at": now,
    }


def build_faction_payload(
    id: str,
    name: str,
    archetype: str,
    description: str,
) -> dict:
    """Return a Faction node property dict ready for upsert_node."""
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "description": description,
        "is_active": True,
        "created_at": now,
        "last_graph_updated_at": now,
    }


def build_npc_payload(
    id: str,
    name: str,
    archetype: str,
    faction_id: str,
    location_id: str,
    biography: str,
    gossipy: int,
    credulity: int,
    honesty: int,
    voice_descriptor: str | None = None,
) -> dict:
    """Return a Character node property dict ready for upsert_node."""
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "faction": faction_id,
        "biography": biography,
        "is_player": False,
        "is_active": True,
        "gossipy": gossipy,
        "credulity": credulity,
        "honesty": honesty,
        "current_mood": "neutral",
        "voice_descriptor": voice_descriptor,
        "created_at": now,
        "updated_at": now,
        "last_graph_updated_at": now,
    }


def build_event_payload(
    id: str,
    summary: str,
    event_type: str,
    location_id: str,
    severity: int,
    is_public: bool = False,
    tick_id: int = 0,
) -> dict:
    """Return an Event node property dict ready for upsert_node."""
    now = _now()
    return {
        "id": id,
        "summary": summary,
        "event_type": event_type,
        "location_id": location_id,
        "severity": severity,
        "is_public": is_public,
        "tick_id": tick_id,
        "occurred_at": now,
        "last_graph_updated_at": now,
    }


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _seed_node(client: EngineClient, node_type: str, payload: dict) -> str:
    """Upsert a node, skipping if it already exists."""
    if client.get_node(node_type, payload["id"]) is not None:
        logger.info("  skip %s/%s (exists)", node_type, payload["id"])
        return "skipped"
    client.upsert_node(node_type, payload)
    logger.info("  created %s/%s", node_type, payload["id"])
    return "created"


def _seed_edge(
    client: EngineClient,
    edge_type: str,
    src_id: str,
    dst_id: str,
    properties: dict | None = None,
) -> str:
    """Upsert an edge (always — graph layer handles idempotency)."""
    client.upsert_edge(edge_type, src_id, dst_id, properties)
    logger.info("  upserted edge %s %s→%s", edge_type, src_id, dst_id)
    return "created"


def _seed_npc_inner_life(
    client: EngineClient,
    npc_id: str,
    beliefs: list[tuple[str, int]],
    goals: list[tuple[str, int]],
    memories: list[tuple[str, int, int]],
    secret: tuple[str, int],
) -> int:
    """Seed beliefs, goals, memories, and one secret for an NPC.

    Passes stable deterministic IDs to every inner-life item so the underlying
    graph layer uses MERGE semantics. Re-calling is idempotent — no duplicates.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        beliefs: List of (content, confidence) tuples.
        goals: List of (description, urgency) tuples.
        memories: List of (content, vividness, emotional_charge) tuples.
        secret: (content, severity) tuple.

    Returns:
        Number of items upserted.
    """
    created = 0
    for content, confidence in beliefs:
        client.post_belief(npc_id, content, confidence, _GAME_TIME, node_id=_belief_id(npc_id, content))
        created += 1
    for n, (description, urgency) in enumerate(goals):
        client.post_goal(npc_id, description, urgency, _GAME_TIME, node_id=_goal_id(npc_id, n))
        created += 1
    for n, (content, vividness, emotional_charge) in enumerate(memories):
        client.post_memory(npc_id, content, vividness, emotional_charge, _GAME_TIME, node_id=_memory_id(npc_id, n))
        created += 1
    content, severity = secret
    client.post_secret(npc_id, content, severity, _GAME_TIME, node_id=_secret_id(npc_id))
    created += 1
    logger.info("  upserted %d inner-life items for %s", created, npc_id)
    return created


# ---------------------------------------------------------------------------
# Tavern world data (tw_ prefix)
# ---------------------------------------------------------------------------

_LOCATIONS = [
    ("tw_tavern", "The Prancing Goat Inn", "tavern", "A busy roadside inn where travellers swap gossip over warm ale."),
    ("tw_market", "Market District", "market", "A compact trading square, loud with haggling and the smell of spices."),
]

_FACTIONS = [
    ("tw_merchants", "Travelling Merchants", "mercantile", "A loose network of merchants who share trade routes and price intelligence."),
    ("tw_innkeepers", "Innkeepers Association", "civic", "A local guild of innkeepers who set standards and share troublemakers' names."),
]

_NPCS = [
    # (id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
    ("tw_innkeeper", "Gwenna", "innkeeper", "tw_innkeepers", "tw_tavern",
     "Runs The Prancing Goat with a sharp ear and a warm hearth — she knows every rumour in town.", 65, 60, 70,
     "Efficient and direct. Runs a clean house and expects the same from her guests."
     " Friendly but not warm — commerce first, gossip a distant second."),
    ("tw_wanderer", "Zephyrin", "bard", "neutral", "tw_tavern",
     "A theatrical travelling bard who trades in stories and claims to have performed in a dozen kingdoms.", 80, 50, 50,
     "Storyteller's cadence. Every answer is a story with a point buried at the end."
     " Pauses theatrically. Names people and places from places you've never heard of."),
    ("tw_merchant", "Corvus", "merchant", "tw_merchants", "tw_market",
     "A practical cloth merchant who moves quickly through towns and trusts no one's word over a signed contract.", 45, 35, 65,
     "Clipped and impatient. Has been haggling for thirty years and has no patience for preamble."
     " Quotes prices, not opinions."),
]

_NPC_MEMBER_OF = [
    ("tw_innkeeper", "tw_innkeepers", "member"),
    ("tw_merchant", "tw_merchants", "member"),
]

_NPC_INNER_LIFE: dict[str, dict] = {
    "tw_innkeeper": {
        "beliefs": [
            ("Regular travellers are the lifeblood of this inn — make them feel at home and they always return.", 75),
            ("Merchants argue loudest about coin when they are afraid of losing it.", 65),
        ],
        "goals": [
            ("Keep the inn stocked and the hearth burning through the coming winter.", 60),
        ],
        "memories": [
            ("The night three merchants came to blows over a disputed trade route — I broke it up with a ladle and made them buy a round.", 80, 50),
            ("A performer once stayed here a whole month and never paid a coin, yet I never wanted them to leave.", 85, 70),
        ],
        "secret": ("She waters down the house wine and pockets the difference.", 50),
    },
    "tw_wanderer": {
        "beliefs": [
            ("Every town has one story everyone knows and one story no one will say aloud.", 80),
            ("A good song can unlock secrets faster than any bribe.", 70),
        ],
        "goals": [
            ("Collect enough local stories to fill a new ballad before moving on.", 75),
        ],
        "memories": [
            ("The night I stumbled on a smugglers' handoff at an inn in the east — I kept playing and pretended not to notice.", 85, -40),
            ("The first time a crowd wept at my song — I learned that night that music is a form of power.", 90, 80),
        ],
        "secret": ("He is quietly gathering information for a noble house that wants intelligence on trade routes.", 70),
    },
    "tw_merchant": {
        "beliefs": [
            ("Market fires are always suspicious — someone always benefits from the chaos.", 75),
            ("Trust is a commodity; some people sell it very cheap.", 70),
        ],
        "goals": [
            ("Source enough winter cloth to corner the local market before the season turns.", 80),
        ],
        "memories": [
            ("The season my entire stock was ruined by a river flood — I rebuilt in three months.", 88, -70),
            ("The first time I bribed a gate official — I told myself it was the last time.", 75, -45),
        ],
        "secret": ("He has been selling cloth with false origin stamps to avoid guild tariffs.", 80),
    },
}

_EVENTS = [
    # (id, summary, event_type, location_id, severity, is_public)
    ("tw_theft_at_market", "A merchant's purse was snatched in the market square", "crime", "tw_market", 55, False),
    ("tw_market_fire", "A small fire broke out at a cloth stall and damaged two nearby stands", "disaster", "tw_market", 40, True),
    ("tw_travelling_performer", "A celebrated bard from the capital has arrived in town and is performing at the inn", "cultural", "tw_tavern", 20, True),
]

# KNOWS_ABOUT: (npc_id, event_id, knowledge_state, distortion_type, distortion_level, distorted_summary)
_KNOWS_ABOUT = [
    ("tw_innkeeper", "tw_theft_at_market",
     "witnessed", None, 0,
     "I saw it myself — a young man in a grey cloak bumped into the cloth merchant and had his purse away before anyone looked twice."),
    ("tw_merchant", "tw_market_fire",
     "rumor", "minimization", 25,
     "I heard there was a fire, but they say it was just a candle too close to a bolt of linen. Nothing serious, apparently."),
    ("tw_wanderer", "tw_travelling_performer",
     "fact", None, 0,
     "Mira Solen is here — a singer of some renown in the capital. I have heard her perform before. She is the real thing."),
]

_NPC_LOCATED_AT = [
    ("tw_innkeeper", "tw_tavern"),
    ("tw_wanderer", "tw_tavern"),
    ("tw_merchant", "tw_market"),
]


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------


def seed_all(client: EngineClient) -> dict:
    """Seed the tavern eval world via the NPC Engine HTTP API.

    Dependency order:
    1. Locations
    2. Factions
    3. Characters
    4. MEMBER_OF edges
    5. NPC inner life (stable IDs — idempotent via MERGE)
    6. Events
    7. KNOWS_ABOUT edges
    8. LOCATED_AT edges

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

    logger.info("[seed-tavern] Locations")
    for loc_id, name, tag, descriptor in _LOCATIONS:
        _tally(_seed_node(client, "Location", build_location_payload(loc_id, name, tag, descriptor)))

    logger.info("[seed-tavern] Factions")
    for faction_id, name, archetype, description in _FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))

    logger.info("[seed-tavern] Characters")
    for npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor in _NPCS:
        _tally(_seed_node(
            client,
            "Character",
            build_npc_payload(npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor),
        ))

    logger.info("[seed-tavern] MEMBER_OF edges")
    for npc_id, faction_id, role in _NPC_MEMBER_OF:
        _tally(_seed_edge(client, "MEMBER_OF", npc_id, faction_id, {
            "role": role,
            "status": "active",
            "joined_at": _now(),
        }))

    logger.info("[seed-tavern] NPC inner life")
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

    logger.info("[seed-tavern] Events")
    for evt_id, summary, event_type, location_id, severity, is_public in _EVENTS:
        _tally(_seed_node(
            client,
            "Event",
            build_event_payload(
                id=evt_id,
                summary=summary,
                event_type=event_type,
                location_id=location_id,
                severity=severity,
                is_public=is_public,
            ),
        ))

    logger.info("[seed-tavern] KNOWS_ABOUT edges")
    for npc_id, event_id, knowledge_state, distortion_type, distortion_level, distorted_summary in _KNOWS_ABOUT:
        _tally(_seed_edge(client, "KNOWS_ABOUT", npc_id, event_id, {
            "knowledge_state": knowledge_state,
            "distortion_type": distortion_type,
            "distortion_level": distortion_level,
            "distorted_summary": distorted_summary,
            "learned_at_tick": 0,
            "source_character_id": None,
        }))

    logger.info("[seed-tavern] LOCATED_AT edges")
    for npc_id, loc_id in _NPC_LOCATED_AT:
        _tally(_seed_edge(client, "LOCATED_AT", npc_id, loc_id, {
            "is_permanent_resident": True,
            "arrived_at": _now(),
        }))

    logger.info("[seed-tavern] Done — created=%d skipped=%d", created, skipped)
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Seed the tavern eval world via the NPC Engine HTTP API.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NPC_BASE_URL", "http://localhost:8000"),
        help="NPC Engine base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY_SECRET", "eval-key-change-me"),
        help="Bearer token (default: eval-key-change-me or API_KEY_SECRET env var)",
    )
    args = parser.parse_args()

    from demo_game.client import EngineClient

    client = EngineClient(args.base_url, args.api_key)
    try:
        result = seed_all(client)
        print(f"Tavern world seed complete — created={result['created']} skipped={result['skipped']}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
