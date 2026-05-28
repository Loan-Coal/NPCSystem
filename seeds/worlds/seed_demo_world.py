"""
Module: seed_demo_world
Layer: demo_game (external client)
Purpose: Seed the demo world via the NPC Engine HTTP API. Idempotent on re-run.
Dependencies: demo_game.client, demo_game.config
Used by: make demo-seed, demo_game/tests/test_seed.py, __main__

SYNC NOTE: Keep aligned with src/npc_engine/data/api_seeder.py.
When either seeder adds a new node type or resource, review the other.
See project-harness/DECISIONS.md DEC-020, DEC-021, DEC-022 for the seeder conventions.

300-line exception: inline NPC data (beliefs/goals/memories/secrets) cannot be
split without an artificial data-only module that exists solely to be imported
back here.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GAME_TIME: dict = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
_WORLD_STATE_ID = "world"


# ---------------------------------------------------------------------------
# Builder functions (pure — no I/O)
# ---------------------------------------------------------------------------


def build_location_payload(
    id: str,
    name: str,
    location_tag: str,
    descriptor: str,
) -> dict:
    """Return a Location node property dict ready for upsert_node.

    Args:
        id: Stable node ID, e.g. "loc_tavern".
        name: Human-readable display name.
        location_tag: Short tag used by the engine for archetype logic.
        descriptor: One-sentence description of the location.

    Returns:
        Dict with all required Location properties.
    """
    now = _now()
    return {
        "id": id,
        "name": name,
        "location_tag": location_tag,
        "descriptor": descriptor,
        "region": "city",
        "last_graph_updated_at": now,
    }


def build_faction_payload(
    id: str,
    name: str,
    archetype: str,
    description: str,
) -> dict:
    """Return a Faction node property dict ready for upsert_node.

    Args:
        id: Stable faction ID, e.g. "merchants_guild".
        name: Human-readable faction name.
        archetype: Faction archetype (mercantile, military, criminal, etc.).
        description: One-sentence description.

    Returns:
        Dict with all required Faction properties.
    """
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
    """Return a Character node property dict ready for upsert_node.

    Args:
        id: Stable character ID, e.g. "mira_innkeeper".
        name: Display name.
        archetype: Character archetype (innkeeper, merchant, guard_captain, etc.).
        faction_id: Faction node ID or "neutral".
        location_id: Home location node ID.
        biography: One-sentence biography.
        gossipy: Tendency to spread information (0–100).
        credulity: Tendency to believe information (0–100).
        honesty: Tendency to tell the truth (0–100).
        voice_descriptor: Optional LLM voice/tone guidance string for the dialogue prompt.

    Returns:
        Dict with all required Character properties.
    """
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
    """Return an Event node property dict ready for upsert_node.

    Args:
        id: Stable event ID, e.g. "northern_war_begins".
        summary: Short description of what happened.
        event_type: Event category (conflict, discovery, crime, etc.).
        location_id: Where the event occurred.
        severity: How impactful the event is (0–100).
        is_public: Whether the event is broadly known.
        tick_id: Game tick at which the event occurred.

    Returns:
        Dict with all required Event properties.
    """
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


def build_world_state_payload(
    epoch: str,
    active_conditions: list[str],
) -> dict:
    """Return a world_state node property dict.

    Args:
        epoch: Current epoch name (e.g. "peace", "war").
        active_conditions: List of active condition IDs.

    Returns:
        Dict with all required world_state properties.
    """
    now = _now()
    return {
        "id": _WORLD_STATE_ID,
        "epoch": epoch,
        "active_conditions": active_conditions,
        "faction_standings": {},
        "time_of_day": "morning",
        "weather": "clear",
        "last_updated_at": now,
        "last_graph_updated_at": now,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _seed_node(
    client: EngineClient,
    node_type: str,
    payload: dict,
) -> str:
    """Upsert a node if it does not already exist.

    Returns:
        "created" or "skipped".
    """
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
    """Upsert an edge if it does not already exist.

    Returns:
        "created" or "skipped".
    """
    if client.get_edge(edge_type, src_id, dst_id) is not None:
        logger.info("  skip edge %s %s→%s (exists)", edge_type, src_id, dst_id)
        return "skipped"
    client.upsert_edge(edge_type, src_id, dst_id, properties)
    logger.info("  created edge %s %s→%s", edge_type, src_id, dst_id)
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

    Uses BELIEVES edge count as idempotency proxy: if the NPC already has any
    BELIEVES edges, all inner-life seeding for this NPC is skipped.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        beliefs: List of (content, confidence) tuples.
        goals: List of (description, urgency) tuples.
        memories: List of (content, vividness, emotional_charge) tuples.
        secret: (content, severity) tuple.

    Returns:
        Number of items created (0 if skipped).
    """
    if client.get_beliefs(npc_id):
        logger.info("  skip inner life for %s (already seeded)", npc_id)
        return 0

    created = 0
    for content, confidence in beliefs:
        client.post_belief(npc_id, content, confidence, _GAME_TIME)
        created += 1

    for description, urgency in goals:
        client.post_goal(npc_id, description, urgency, _GAME_TIME)
        created += 1

    for content, vividness, emotional_charge in memories:
        client.post_memory(npc_id, content, vividness, emotional_charge, _GAME_TIME)
        created += 1

    content, severity = secret
    client.post_secret(npc_id, content, severity, _GAME_TIME)
    created += 1

    logger.info("  created %d inner-life items for %s", created, npc_id)
    return created


# ---------------------------------------------------------------------------
# Demo world data
# ---------------------------------------------------------------------------

_LOCATIONS = [
    ("loc_tavern", "The Rusty Flagon", "tavern", "A well-worn tavern where travelers and locals share ale and secrets."),
    ("loc_market_square", "Market Square", "market", "The beating heart of commerce, loud with haggling and rumor."),
    ("loc_guard_barracks", "Guard Barracks", "barracks", "The disciplined quarters of the city guard, smelling of iron and duty."),
]

_FACTIONS = [
    ("merchants_guild", "Merchants Guild", "mercantile", "Controls the flow of trade through the city."),
    ("city_guard", "City Guard", "military", "Enforces the law and defends the city walls."),
    ("thieves_guild", "Thieves Guild", "criminal", "A shadow organization that lives in the cracks of the city."),
]

# Faction-faction relations via STANDS_WITH (negative standing = antagonism)
_FACTION_STANDS_WITH = [
    ("merchants_guild", "thieves_guild", -60),
    ("city_guard", "thieves_guild", -80),
]

_NPCS = [
    # (id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
    ("mira_innkeeper", "Mira", "innkeeper", "neutral", "loc_tavern",
     "Runs the Rusty Flagon with an even hand and a sharp ear.", 60, 55, 70,
     "Warm, observant. Cautious about politics — never says more than she needs to."
     " Frames hard news as rumour or second-hand. Invites the listener to share what they know in return."),
    ("aldric_merchant", "Aldric", "merchant", "merchants_guild", "loc_market_square",
     "A veteran spice trader who knows every coin's worth and every man's price.", 50, 40, 65,
     "Measured and precise. Every statement is a negotiation — he gives only what serves him."
     " Refers to value, leverage, and risk. Distrusts sentiment."),
    ("captain_sorn", "Captain Sorn", "guard_captain", "city_guard", "loc_guard_barracks",
     "Commands the city watch with iron discipline and growing dread.", 25, 35, 85,
     "Clipped military diction. Direct. Names the enemy without emotion or hesitation."
     " No hedging, no qualifiers. Every sentence lands like a report to a superior officer."),
    ("lira_fence", "Lira", "fence", "thieves_guild", "loc_tavern",
     "Moves stolen goods with a smile and a story, always one step ahead.", 75, 45, 30,
     "Light, deflective. Turns every question into a joke or a counter-question."
     " Never volunteers information — makes you earn it. Laughs easily; means very little of it."),
    ("old_henryk", "Old Henryk", "elder", "neutral", "loc_market_square",
     "A retired courier who has seen three wars and remembers every one.", 80, 70, 80,
     "Rambling. Mixes current rumour with personal memories from decades ago."
     " Speaks with complete confidence even about details he has wrong. Never hedges."),
]

# NPC faction membership: (npc_id, faction_id, role)
_NPC_MEMBER_OF = [
    ("aldric_merchant", "merchants_guild", "officer"),
    ("captain_sorn", "city_guard", "officer"),
    ("lira_fence", "thieves_guild", "member"),
]

# Inner life: keyed by npc_id
_NPC_INNER_LIFE: dict[str, dict] = {
    "mira_innkeeper": {
        "beliefs": [
            ("The war will come here eventually — I have seen it before.", 70),
            ("People reveal their true nature after the second drink.", 80),
        ],
        "goals": [
            ("Keep the Rusty Flagon a neutral ground where all factions are welcome.", 60),
        ],
        "memories": [
            ("The night a deserter begged at my door in the rain. I hid him in the cellar for a week.", 85, 65),
            ("The last time the city went to war — half my regulars never came back.", 90, -75),
        ],
        "secret": ("She hid a deserter from the city guard last winter.", 75),
    },
    "aldric_merchant": {
        "beliefs": [
            ("The guild protects those who pay their dues — and devours those who don't.", 65),
            ("Thieves are a plague on honest commerce and should be hanged.", 85),
        ],
        "goals": [
            ("Corner the northern spice trade before the war closes the roads.", 70),
            ("Expose the guild spy who has been skimming from the market accounts.", 55),
        ],
        "memories": [
            ("The night the south warehouse burned. I saw the guild master watching from across the street.", 88, 80),
            ("The day I signed my first guild contract — I did not read it carefully enough.", 70, -50),
        ],
        "secret": ("He has been skimming a tenth from his own guild tithe for two years.", 80),
    },
    "captain_sorn": {
        "beliefs": [
            ("The thieves guild is planning something large — the signs are all there.", 90),
            ("The city walls have never been in worse repair. One hard winter could break us.", 75),
        ],
        "goals": [
            ("Catch Lira in a crime significant enough to break the guild's protection racket.", 80),
        ],
        "memories": [
            ("The morning I found the gate sergeant's bribe money hidden in his boot. I said nothing.", 82, -60),
            ("The day I was promoted to captain — my predecessor disappeared the same week.", 78, 40),
        ],
        "secret": ("He knows the name of the merchant who bribed the gate sergeant and has done nothing.", 70),
    },
    "lira_fence": {
        "beliefs": [
            ("Every guard has a price — you just have to find the right currency.", 80),
            ("Aldric's ledger holds enough guild secrets to bury half the market.", 70),
        ],
        "goals": [
            ("Get that ledger from Aldric before he realizes what it proves.", 85),
        ],
        "memories": [
            ("The night I moved a crate of stolen army supplies through the market. No one asked questions.", 75, 55),
            ("The first time I was caught — I was twelve, and the merchant let me go. I never forgot.", 90, 70),
        ],
        "secret": ("She is currently fencing a shipment of stolen city guard armor.", 90),
    },
    "old_henryk": {
        "beliefs": [
            ("War changes everything about a place — the smell of fear never leaves.", 85),
            ("Young captains always underestimate the thieves until it is too late.", 65),
        ],
        "goals": [
            ("Warn the right people before it is too late — but find out who the right people are first.", 50),
        ],
        "memories": [
            ("Running dispatches through the north pass during the last war. Half my route was behind enemy lines.", 92, -80),
            ("The evening I found the smuggler's cache in the old mill — I marked it and walked away.", 80, 45),
        ],
        "secret": ("He knows the location of an old smuggler's cache beneath the north mill.", 60),
    },
}

# NPC-NPC edges: (edge_type, src_id, dst_id, properties)
_NPC_NPC_EDGES: list[tuple[str, str, str, dict]] = [
    ("RELATES_TO", "mira_innkeeper", "old_henryk", {
        "trust": 70, "affection": 50, "fear": 0,
        "relevance_score": 60, "interaction_count": 10,
        "last_updated_at": "tick_0",
    }),
    ("RELATES_TO", "lira_fence", "aldric_merchant", {
        "trust": 10, "affection": 0, "fear": 30,
        "relevance_score": 80, "interaction_count": 3,
        "last_updated_at": "tick_0",
    }),
    ("OPPOSES", "captain_sorn", "lira_fence", {
        "intensity": 85,
        "reason": "lira runs a criminal operation in the city",
        "established_tick": 0,
    }),
    # captain_sorn has direct, undistorted knowledge of the war (tick 0 seed)
    ("KNOWS_ABOUT", "captain_sorn", "northern_war_begins", {
        "knowledge_state": "knows",
        "distortion_type": None,
        "distortion_level": 0,
        "distorted_summary": "The northern armies have crossed the border. We are at war.",
        "learned_at_tick": 0,
        "source_character_id": None,
    }),
    # Pre-seeded gossip chain for demo reliability (see DEC-006).
    ("KNOWS_ABOUT", "mira_innkeeper", "northern_war_begins", {
        "knowledge_state": "rumor",
        "distortion_type": "exaggeration",
        "distortion_level": 20,
        "distorted_summary": (
            "A soldier passing through told me the northern armies, the Iron Guard he called them,"
            " have moved on the border. Whether it is true I cannot say, but he seemed shaken."
        ),
        "learned_at_tick": 1,
        "source_character_id": "captain_sorn",
    }),
    ("KNOWS_ABOUT", "old_henryk", "northern_war_begins", {
        "knowledge_state": "rumor",
        "distortion_type": "exaggeration",
        "distortion_level": 70,
        "distorted_summary": (
            "I ran dispatches through king's pass in the last war — I know that road."
            " And now they say the northmen have poured through it, thousands dead."
            " Utterly catastrophic, those northmen storming king's pass like that."
        ),
        "learned_at_tick": 2,
        "source_character_id": "mira_innkeeper",
    }),
]

# LOCATED_AT edges: (npc_id, location_id)
_NPC_LOCATED_AT: list[tuple[str, str]] = [
    ("mira_innkeeper", "loc_tavern"),
    ("lira_fence", "loc_tavern"),
    ("aldric_merchant", "loc_market_square"),
    ("old_henryk", "loc_market_square"),
    ("captain_sorn", "loc_guard_barracks"),
]


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------


def seed_all(client: EngineClient) -> dict:
    """Seed the full demo world via the NPC Engine HTTP API.

    Dependency order:
    1. Locations
    2. Factions
    3. Characters
    4. MEMBER_OF edges (NPC ↔ Faction)
    5. Faction-faction STANDS_WITH edges
    6. NPC inner life (beliefs, goals, memories, secrets)
    7. Events
    8. world_state
    9. NPC-NPC structural edges
    10. LOCATED_AT edges

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

    # 1. Locations
    logger.info("[seed] Locations")
    for loc_id, name, tag, descriptor in _LOCATIONS:
        _tally(_seed_node(client, "Location", build_location_payload(loc_id, name, tag, descriptor)))

    # 2. Factions
    logger.info("[seed] Factions")
    for faction_id, name, archetype, description in _FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))

    # 3. Characters
    logger.info("[seed] Characters")
    for npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor in _NPCS:
        _tally(_seed_node(
            client,
            "Character",
            build_npc_payload(npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor),
        ))

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
    _tally(_seed_node(client, "world_state", build_world_state_payload("war", ["northern_war"])))

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

    logger.info("[seed] Done — created=%d skipped=%d", created, skipped)
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import os

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from demo_game.client import EngineClient
    from demo_game.config import config

    base_url = os.environ.get("NPC_BASE_URL", config.NPC_BASE_URL)
    api_key = os.environ.get("NPC_API_KEY", config.NPC_API_KEY)

    client = EngineClient(base_url, api_key)
    try:
        result = seed_all(client)
        print(f"Seed complete — created={result['created']} skipped={result['skipped']}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
