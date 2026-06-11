"""
Module: seed
Layer: demo_game (external client)
Purpose: Seed the demo world via the NPC Engine HTTP API. Idempotent on re-run.
Dependencies: demo_game.client, demo_game.config, demo_game.constants
Used by: make demo-seed, demo_game/tests/test_seed.py

See project-harness/DECISIONS.md DEC-020, DEC-021, DEC-022 for seeder conventions.

300-line exception: inline NPC data (beliefs/goals/memories/secrets) cannot be
split without an artificial data-only module that exists solely to be imported
back here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from demo_game.constants import (
    LOC_ID_CHAPEL,
    NPC_ID_HARWICK_GUARD,
    NPC_ID_NEL_PICKPOCKET,
    NPC_ID_SERA_BARMAID,
)

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GAME_TIME: dict = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
# Prior-era timestamp for is_historical memories (e.g. a war fought long before the
# current year-1 epoch). Marks a memory as long-past so the NPC frames it as a past
# recollection, never the current situation (S26.3, ISSUE-093).
_HISTORICAL_GAME_TIME: dict = {"year": 0, "season": "autumn", "day": 1, "time_of_day": "night"}
_WORLD_STATE_ID = "world"
# Scarcity constraint (S7.2): bribing all 3 factions to win threshold costs 4*20*3=240 gold.
# Starting at 60 the player demonstrably cannot win by bribing alone; must earn via quest/trade.
_PLAYER_STARTING_GOLD = 60


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
        voice_descriptor: Optional LLM voice/tone guidance string.

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


class WorldStatePayload(BaseModel):
    """Typed world_state node property payload for the demo seeder (ISSUE-084).

    `.model_dump()` yields the property dict consumed by the generic node upsert.
    """

    id: str
    epoch: str
    active_conditions: list[str]
    faction_standings: dict[str, int] = Field(default_factory=dict)
    time_of_day: str = "morning"
    weather: str = "clear"
    last_updated_at: str
    last_graph_updated_at: str


def build_world_state_payload(
    epoch: str,
    active_conditions: list[str],
) -> WorldStatePayload:
    """Return a typed world_state node property payload.

    Args:
        epoch: Current epoch name (e.g. "peace", "war").
        active_conditions: List of active condition IDs.

    Returns:
        WorldStatePayload with all required world_state properties.
    """
    now = _now()
    return WorldStatePayload(
        id=_WORLD_STATE_ID,
        epoch=epoch,
        active_conditions=active_conditions,
        last_updated_at=now,
        last_graph_updated_at=now,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


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


def _force_patch_world_state(client: EngineClient) -> None:
    """Force-patch world_state epoch and active_conditions to the demo values.

    Called unconditionally after the _seed_node upsert so that a pre-existing
    node with a drifted epoch (e.g. 'age_of_peace') is always corrected.

    Args:
        client: Live EngineClient instance used to reach the HTTP API.
    """
    client.patch_node(
        "world_state",
        _WORLD_STATE_ID,
        {
            "epoch": "war",
            "active_conditions": ["northern_war"],
        },
    )


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


def _seed_item_edge_if_unowned(
    client: EngineClient,
    owner_id: str,
    item_id: str,
    properties: dict | None = None,
) -> str:
    """Seed OWNS(owner→item) only when no character currently owns the item.

    Unlike _seed_edge, this checks all inbound OWNS edges on the item (not just the
    specific owner→item edge). This prevents re-gifting items that were transferred
    during gameplay — e.g. the player delivers the amulet to Aldric, then reseed
    would otherwise recreate OWNS(player→amulet) because that specific edge no longer
    exists, even though Aldric now owns it.

    Args:
        client: Authenticated EngineClient.
        owner_id: Character ID who should own the item on first seed.
        item_id: Item node ID.
        properties: Optional edge properties (e.g. acquired_at).

    Returns:
        "created" or "skipped".
    """
    current_owners = client.get_graph_edges("OWNS", dst_id=item_id, limit=1)
    if current_owners:
        logger.info("  skip edge OWNS %s→%s (item already owned)", owner_id, item_id)
        return "skipped"
    client.upsert_edge("OWNS", owner_id, item_id, properties or {})
    logger.info("  created edge OWNS %s→%s", owner_id, item_id)
    return "created"


def _seed_memories(
    client: EngineClient,
    npc_id: str,
    memories: list[tuple[str, int, int] | tuple[str, int, int, bool]],
) -> int:
    """Seed an NPC's memories; a 4th tuple element flags a historical (prior-era) memory.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        memories: (content, vividness, emotional_charge[, is_historical]) tuples.
    Returns:
        Number of memories upserted.
    """
    for n, mem in enumerate(memories):
        is_historical = bool(mem[3]) if len(mem) > 3 else False
        occurred = _HISTORICAL_GAME_TIME if is_historical else None
        client.post_memory(
            npc_id, mem[0], mem[1], mem[2], _GAME_TIME,
            node_id=_memory_id(npc_id, n),
            occurred_at_game_time=occurred,
            is_historical=is_historical,
        )
    return len(memories)


def _seed_npc_inner_life(
    client: EngineClient,
    npc_id: str,
    beliefs: list[tuple[str, int]],
    goals: list[tuple[str, int]],
    memories: list[tuple[str, int, int] | tuple[str, int, int, bool]],
    secret: tuple[str, int],
) -> int:
    """Seed beliefs, goals, memories, and one secret for an NPC.

    Passes stable deterministic IDs to every inner-life item so the underlying
    graph layer uses MERGE semantics. Re-calling this function is idempotent —
    no duplicate nodes are created regardless of prior seed runs.

    Args:
        client: Engine client.
        npc_id: Target character node ID.
        beliefs: List of (content, confidence) tuples.
        goals: List of (description, urgency) tuples.
        memories: List of (content, vividness, emotional_charge) tuples; an optional
            4th bool element marks the memory as historical (a prior-era recollection).
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

    created += _seed_memories(client, npc_id, memories)

    content, severity = secret
    client.post_secret(npc_id, content, severity, _GAME_TIME, node_id=_secret_id(npc_id))
    created += 1

    logger.info("  upserted %d inner-life items for %s", created, npc_id)
    return created


def _seed_location_hierarchy(client: EngineClient) -> int:
    """Seed the city-level location hierarchy for the demo world (EXP-87).

    Creates a ``loc_city`` Location node and wires the three existing demo
    locations into it via PART_OF edges. All calls use MERGE semantics so
    this function is idempotent on repeated runs.

    Args:
        client: Authenticated EngineClient.

    Returns:
        Number of items created or upserted.
    """
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

    # EXP-223: loc_chapel added to the city hierarchy.
    _child_locations = ["loc_tavern", "loc_market_square", "loc_guard_barracks", LOC_ID_CHAPEL]
    for child_id in _child_locations:
        client.post_part_of(child_id, "loc_city", hierarchy_level=0)
        logger.info("  upserted PART_OF %s → loc_city", child_id)

    return len(_child_locations) + 1  # +1 for loc_city node


# ---------------------------------------------------------------------------
# Demo world data
# ---------------------------------------------------------------------------

_LOCATIONS = [
    ("loc_tavern", "The Rusty Flagon", "tavern", "A well-worn tavern where travelers and locals share ale and secrets."),
    ("loc_market_square", "Market Square", "market", "The beating heart of commerce, loud with haggling and rumor."),
    ("loc_guard_barracks", "Guard Barracks", "barracks", "The disciplined quarters of the city guard, smelling of iron and duty."),
    # EXP-223: new chapel location — quiet neutral ground between factions.
    (LOC_ID_CHAPEL, "The Chapel", "chapel", "A soot-stained stone chapel; the one place all factions leave alone."),
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
    # EXP-223: three new NPCs within existing factions
    (NPC_ID_SERA_BARMAID, "Sera", "barmaid", "neutral", "loc_tavern",
     "Mira's assistant, quick with a cloth and quicker with her ears.", 70, 65, 60,
     "Friendly and light, but vague when asked directly. Deflects with chores and small talk."),
    (NPC_ID_HARWICK_GUARD, "Harwick", "guard", "city_guard", "loc_guard_barracks",
     "A rank-and-file soldier who follows orders and tries not to think too hard.", 30, 60, 75,
     "Blunt and literal. Trusts his officers. Uncomfortable with ambiguity."),
    (NPC_ID_NEL_PICKPOCKET, "Nel", "pickpocket", "thieves_guild", "loc_tavern",
     "A young guild runner who moves between tables and pockets without anyone noticing.", 65, 55, 25,
     "Evasive, fast-talking. Denies everything. Pretends to be younger and more innocent than she is."),
]

# NPC faction membership: (npc_id, faction_id, role)
# EXP-223: harwick_guard and nel_pickpocket added to existing factions.
_NPC_MEMBER_OF = [
    ("aldric_merchant", "merchants_guild", "officer"),
    ("captain_sorn", "city_guard", "officer"),
    ("lira_fence", "thieves_guild", "member"),
    (NPC_ID_HARWICK_GUARD, "city_guard", "soldier"),
    (NPC_ID_NEL_PICKPOCKET, "thieves_guild", "runner"),
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
            ("A stranger came in asking about the northern war. Nervous eyes, too many questions. I told them what little I knew.", 80, 30),
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
            ("Running dispatches through the north pass during the last war. Half my route was behind enemy lines.", 92, -80, True),
            ("The evening I found the smuggler's cache in the old mill — I marked it and walked away.", 80, 45),
        ],
        "secret": ("He knows the location of an old smuggler's cache beneath the north mill.", 60),
    },
    # EXP-223: inner life for the three new NPCs
    NPC_ID_SERA_BARMAID: {
        "beliefs": [
            ("The Rusty Flagon is the safest place in the city — as long as Mira keeps it neutral.", 70),
            ("People talk too freely after the second round. I make sure to remember.", 75),
        ],
        "goals": [
            ("Save enough to leave the city before the war reaches the gates.", 55),
        ],
        "memories": [
            ("A hooded man slipped Lira a folded note last Tenday. Neither noticed me refilling their cups.", 78, 40),
            ("The night a drunk guard let slip where the captain hides his private ledger.", 82, 50),
        ],
        "secret": ("She has been passing small items to a guild contact — unaware she is being used as a dead drop.", 65),
    },
    NPC_ID_HARWICK_GUARD: {
        "beliefs": [
            ("The captain's orders come down clean and you follow them. That is the whole job.", 80),
            ("Something is off at the south gate — the sergeant is too relaxed for a wartime posting.", 55),
        ],
        "goals": [
            ("Get through this posting without ending up on the wrong side of the captain's temper.", 60),
        ],
        "memories": [
            ("The morning a merchant bribed the gate sergeant and I pretended not to see.", 70, -45),
            ("Drill practice the week before the war declaration — nobody believed the orders were real.", 65, 30),
        ],
        "secret": ("He reported the bribe anonymously to the watch but the note was never acknowledged.", 50),
    },
    NPC_ID_NEL_PICKPOCKET: {
        "beliefs": [
            ("Everyone in this city is running a con. The only difference is how big.", 80),
            ("Lira is testing me. Every job she gives me is a test.", 70),
        ],
        "goals": [
            ("Prove herself to Lira by lifting something from the merchant quarter without getting caught.", 75),
        ],
        "memories": [
            ("The first purse I ever cut — a guild veteran's, as a test. He let me keep three coins.", 85, 60),
            ("Hiding under a market stall when the guard swept the square looking for a thief. Not me, that time.", 75, 35),
        ],
        "secret": ("She took a personal ring from the last job and hid it — Lira does not know yet.", 70),
    },
}

# NPC Needs: (npc_id, kind, level 0-100 where 0=critical, decay_rate per tick)
_NPC_NEEDS: list[tuple[str, str, int, int]] = [
    # mira_innkeeper — busy social hub, rests poorly
    ("mira_innkeeper", "social",     85, 2),
    ("mira_innkeeper", "rest",       35, 4),
    # aldric_merchant — driven, skips meals
    ("aldric_merchant", "hunger",    28, 3),
    ("aldric_merchant", "social",    60, 2),
    # captain_sorn — disciplined but exhausted
    ("captain_sorn", "rest",         20, 5),
    ("captain_sorn", "recreation",   45, 2),
    # lira_fence — cautious, keeps to herself
    ("lira_fence", "social",         70, 2),
    ("lira_fence", "rest",           55, 3),
    # old_henryk — worn down, needs rest most
    ("old_henryk", "rest",           15, 4),
    ("old_henryk", "hunger",         50, 3),
    # EXP-223 new NPCs
    # sera_barmaid — always on her feet, socially fulfilled but physically exhausted
    (NPC_ID_SERA_BARMAID, "rest",    25, 5),
    (NPC_ID_SERA_BARMAID, "social",  75, 1),
    # harwick_guard — disciplined routine, bored from repetitive duty
    (NPC_ID_HARWICK_GUARD, "recreation", 30, 2),
    (NPC_ID_HARWICK_GUARD, "rest",       55, 3),
    # nel_pickpocket — anxious, high social need (information gathering)
    (NPC_ID_NEL_PICKPOCKET, "social",    80, 3),
    (NPC_ID_NEL_PICKPOCKET, "hunger",    40, 4),
]

# Leverage nodes: (id, demand, status, created_at_tick)
_LEVERAGE_NODES: list[tuple[str, str, str, int]] = [
    (
        "lv_lira_over_aldric",
        "Reveal that Aldric has been skimming guild tithes unless he lets a shipment through",
        "held",
        0,
    ),
    (
        "lv_sorn_over_gate_sgt",
        "Demand the gate sergeant's loyalty in exchange for silence about the bribe",
        "held",
        0,
    ),
]

# HAS_LEVERAGE edges: (holder_npc_id, leverage_node_id)
_HAS_LEVERAGE_EDGES: list[tuple[str, str]] = [
    ("lira_fence", "lv_lira_over_aldric"),
    ("captain_sorn", "lv_sorn_over_gate_sgt"),
]

# ---------------------------------------------------------------------------
# Military layer — armies for S6.6 battle demo
# ---------------------------------------------------------------------------

# Extra faction for the Iron Legion (northern invaders from northern_war_begins event)
_MILITARY_FACTIONS: list[tuple[str, str, str, str]] = [
    ("iron_legion", "Iron Legion", "military", "The northern army that crossed the border at the start of the war."),
]

# Army nodes: (id, faction_id, strength, current_location_id, composition)
_ARMIES: list[tuple[str, str, int, str, str]] = [
    (
        "army_iron_legion",
        "iron_legion",
        100,
        "loc_guard_barracks",
        '{"infantry": 80, "cavalry": 15, "siege": 5}',
    ),
    (
        "army_city_guard_main",
        "city_guard",
        60,
        "loc_guard_barracks",
        '{"infantry": 55, "cavalry": 5, "siege": 0}',
    ),
]

# OCCUPIES edges: (army_id, location_id, since_tick)
_ARMY_OCCUPIES: list[tuple[str, str, int]] = [
    ("army_iron_legion", "loc_guard_barracks", 0),
    ("army_city_guard_main", "loc_guard_barracks", 0),
]

# Pledge seed data: (pledger_id, pledgee_id, pledge_type, tick)
# Using create_pledge via the typed pledges route (POST /v1/pledges/characters/{pledger_id})
_PLEDGE_SEED: list[tuple[str, str, str, int]] = [
    ("lira_fence", "thieves_guild", "fealty", 0),
    ("aldric_merchant", "merchants_guild", "fealty", 0),
]

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
        # S26.3 (ISSUE-093): the firsthand past-war clause ("I ran dispatches through
        # king's pass in the last war") was split out into old_henryk's is_historical
        # memory. This rumour is current-war hearsay only — no firsthand framing.
        "distorted_summary": (
            "Word reached me the northmen have poured through king's pass, thousands dead."
            " Utterly catastrophic, they say — the northmen storming king's pass like that."
        ),
        "learned_at_tick": 2,
        "source_character_id": "mira_innkeeper",
    }),
    # Lira hears about the market fire through the tavern (fire is public; word spreads fast).
    ("KNOWS_ABOUT", "lira_fence", "market_fire", {
        "knowledge_state": "rumor",
        "distortion_type": None,
        "distortion_level": 10,
        "distorted_summary": (
            "Word spread through the tavern fast — fire in the square."
            " My kind of chaos, all those distracted guards."
        ),
        "learned_at_tick": 3,
        "source_character_id": None,
    }),
]

# LOCATED_AT edges: (npc_id, location_id)
# EXP-223: three new NPCs added at their home locations.
_NPC_LOCATED_AT: list[tuple[str, str]] = [
    ("mira_innkeeper", "loc_tavern"),
    ("lira_fence", "loc_tavern"),
    ("aldric_merchant", "loc_market_square"),
    ("old_henryk", "loc_market_square"),
    ("captain_sorn", "loc_guard_barracks"),
    (NPC_ID_SERA_BARMAID, "loc_tavern"),
    (NPC_ID_HARWICK_GUARD, "loc_guard_barracks"),
    (NPC_ID_NEL_PICKPOCKET, "loc_tavern"),
]


_PLAYER_ID = "player_demo"
_AMULET_ID = "ancient_amulet"
_ALDRIC_QUEST_ID = "aldric_deliver_quest"
_ALDRIC_REWARD_AMOUNT = 50
_SPICE_ID = "northern_spice_bundle"
_SPICE_VALUE = 120


# ---------------------------------------------------------------------------
# Quest seeding (non-fatal — requires quest engine to be running)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Quest UNLOCKS chains (EXP-19)
# ---------------------------------------------------------------------------

_QUEST_UNLOCKS_CHAINS: list[tuple[str, str, str]] = [
    ("demo_patrol_duty", "demo_captain_report", "complete"),
    ("demo_missing_goods", "demo_fence_confrontation", "complete"),
]

# Chain-target Quest nodes that must exist before UNLOCKS edges are wired (EXP-19 slice-3).
# These are the successor quests unlocked by _QUEST_UNLOCKS_CHAINS above.
_CHAIN_QUESTS: list[dict] = [
    {
        "id": "demo_captain_report",
        "description": "Report the patrol findings to the Captain.",
        "quest_giver_id": "captain_sorn",
        "success_condition": "Deliver the patrol report to Captain Sorn.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "demo_fence_confrontation",
        "description": "Confront Lira about the missing goods.",
        "quest_giver_id": "lira_fence",
        "success_condition": "Speak with Lira at the tavern about the missing shipment.",
        "status": "offered",
        "severity": 50,
    },
]


# Source/trigger Quest nodes for the UNLOCKS chains (EXP-19 slice-4).
# These must exist so the chains can be fired by completing them.
_SOURCE_CHAIN_QUESTS: list[dict] = [
    {
        "id": "demo_patrol_duty",
        "description": "Patrol the northern road and report any suspicious activity.",
        "quest_giver_id": "captain_sorn",
        "success_condition": "Complete the patrol route and return to Captain Sorn.",
        "status": "offered",
        "severity": 35,
    },
    {
        "id": "demo_missing_goods",
        "description": "Investigate what happened to Aldric's missing shipment.",
        "quest_giver_id": "aldric_merchant",
        "success_condition": "Find out what happened to the missing goods.",
        "status": "offered",
        "severity": 45,
    },
]


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
                _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
                logger.info("[seed] Source chain quest seeded: %s", quest_id)
            else:
                logger.info("[seed] Source chain quest %s already exists — skipped", quest_id)
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
                _seed_edge(client, "HAS_QUEST", quest["quest_giver_id"], quest_id, {})
                logger.info("[seed] Chain quest seeded: %s", quest_id)
            else:
                logger.info("[seed] Chain quest %s already exists — skipped", quest_id)
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
        payload = build_npc_payload(npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
        if npc_id == "aldric_merchant":
            payload["currency_balance"] = 200
        _tally(_seed_node(client, "Character", payload))

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

    # 15. NPC Needs
    logger.info("[seed] NPC Needs")
    for npc_id, kind, level, decay_rate in _NPC_NEEDS:
        node_id = f"{npc_id}_need_{kind}"
        _tally(_seed_node(client, "Need", {
            "id": node_id,
            "kind": kind,
            "level": level,
            "decay_rate": decay_rate,
            "character_id": npc_id,
        }))

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

    # 17. Military layer — iron_legion faction + armies + OCCUPIES edges
    logger.info("[seed] Military factions")
    for faction_id, name, archetype, description in _MILITARY_FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))

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

    # 12. Location hierarchy (EXP-87)
    logger.info("[seed] Location hierarchy")
    hierarchy_created = _seed_location_hierarchy(client)
    created += hierarchy_created

    # 13. Quest UNLOCKS chains (EXP-19)
    logger.info("[seed] Quest UNLOCKS chains")
    created += _seed_quest_unlocks_chains(client)

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
