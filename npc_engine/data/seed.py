"""
seed.py - Idempotent seed routines for locations, characters, relations, events, and world state.

Does NOT: run API server lifecycle or scheduler ticks.

Dependencies injected: Settings.
"""

import asyncio
from datetime import datetime, timezone

from graph.db import GraphDB
from config import get_settings


CYPHER_SEED_LOCATIONS = """
UNWIND $locations AS location
MERGE (loc:Location {id: location.id})
SET loc += location
"""

CYPHER_SEED_CHARACTERS = """
UNWIND $characters AS character
MERGE (c:Character {id: character.id})
SET c += character
"""

CYPHER_SEED_LOCATED_AT = """
UNWIND $pairs AS pair
MATCH (c:Character {id: pair.character_id}), (loc:Location {id: pair.location_id})
MERGE (c)-[r:LOCATED_AT]->(loc)
SET r.arrived_at = datetime(), r.is_permanent_resident = pair.is_permanent_resident
"""

CYPHER_SEED_WORLD = """
MERGE (w:WorldState {id: 'world'})
SET w.epoch = 'age_of_peace',
    w.faction_standings = '{}',
    w.active_conditions = '[]',
    w.weather = 'clear',
    w.last_updated_at = datetime()
"""

CYPHER_SEED_RELATIONS = """
MATCH (a:Character), (b:Character)
WHERE a.id <> b.id
    AND a.is_player = false
    AND b.is_player = false
    AND (a.faction = b.faction OR a.current_location_id = b.current_location_id)
MERGE (a)-[r:RELATES_TO]->(b)
SET r.trust = 50,
        r.fear = 50,
        r.affection = 50,
        r.interaction_count = coalesce(r.interaction_count, 0),
        r.delta_log = '[]',
        r.last_updated_at = datetime(),
        r.relevance_score = CASE
            WHEN a.faction = b.faction THEN 1.0
            WHEN a.current_location_id = b.current_location_id THEN 0.5
            ELSE 0.0
        END
"""

CYPHER_SEED_EVENTS = """
UNWIND $events AS event
MERGE (e:Event {id: event.id})
SET e += event
"""

CYPHER_SEED_PARTICIPATION = """
UNWIND $participation AS row
MATCH (c:Character {id: row.character_id}), (e:Event {id: row.event_id})
MERGE (c)-[p:PARTICIPATED_IN]->(e)
SET p.role = row.role,
        p.participated_at = datetime()
"""

CYPHER_SEED_KNOWLEDGE = """
UNWIND $knowledge AS row
MATCH (c:Character {id: row.character_id}), (e:Event {id: row.event_id})
MERGE (c)-[k:KNOWS_ABOUT]->(e)
SET k.knowledge_state = row.knowledge_state,
        k.learned_at_tick = row.learned_at_tick,
        k.distortion_type = row.distortion_type,
        k.distortion_level = row.distortion_level,
        k.distorted_summary = row.distorted_summary,
        k.source_character_id = row.source_character_id
"""


def _locations() -> list[dict]:
    return [
        {"id": "loc_tavern", "name": "Iron Lantern", "region": "North", "location_tag": "tavern", "descriptor": "A busy tavern."},
        {"id": "loc_market", "name": "Grand Market", "region": "Central", "location_tag": "market", "descriptor": "Crowded stalls."},
        {"id": "loc_keep", "name": "Stone Keep", "region": "Central", "location_tag": "keep", "descriptor": "Fortified keep."},
        {"id": "loc_docks", "name": "Salt Docks", "region": "South", "location_tag": "docks", "descriptor": "Trading harbor."},
        {"id": "loc_temple", "name": "Sun Temple", "region": "East", "location_tag": "temple", "descriptor": "Quiet sanctuary."},
    ]


def _characters() -> list[dict]:
    base_time = datetime.now(timezone.utc).isoformat()
    return [
        {"id": "player_1", "name": "Player", "archetype": "adventurer", "faction": "free", "biography": "A wandering player.", "current_location_id": "loc_market", "is_player": True, "created_at": base_time, "updated_at": base_time, "gossipy": 50, "credulity": 50, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_1", "name": "Aldric", "archetype": "merchant", "faction": "guild", "biography": "Veteran merchant.", "current_location_id": "loc_market", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 70, "credulity": 45, "honesty": 65, "current_mood": "neutral"},
        {"id": "npc_2", "name": "Sera", "archetype": "guard", "faction": "guard", "biography": "City guard captain.", "current_location_id": "loc_keep", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 30, "credulity": 35, "honesty": 80, "current_mood": "neutral"},
        {"id": "npc_3", "name": "Mira", "archetype": "healer", "faction": "temple", "biography": "Temple healer.", "current_location_id": "loc_temple", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 45, "credulity": 65, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_4", "name": "Garr", "archetype": "sailor", "faction": "dockers", "biography": "Dock foreman.", "current_location_id": "loc_docks", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 80, "credulity": 55, "honesty": 40, "current_mood": "neutral"},
        {"id": "npc_5", "name": "Lenna", "archetype": "barkeep", "faction": "free", "biography": "Runs the tavern.", "current_location_id": "loc_tavern", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 85, "credulity": 50, "honesty": 55, "current_mood": "neutral"},
        {"id": "npc_6", "name": "Ivor", "archetype": "scribe", "faction": "guild", "biography": "Guild record keeper.", "current_location_id": "loc_market", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 35, "credulity": 40, "honesty": 70, "current_mood": "neutral"},
        {"id": "npc_7", "name": "Rook", "archetype": "thief", "faction": "free", "biography": "Streetwise pickpocket.", "current_location_id": "loc_market", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 90, "credulity": 45, "honesty": 25, "current_mood": "neutral"},
        {"id": "npc_8", "name": "Bran", "archetype": "guard", "faction": "guard", "biography": "Gate sentry.", "current_location_id": "loc_keep", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 25, "credulity": 40, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_9", "name": "Thalia", "archetype": "acolyte", "faction": "temple", "biography": "Young acolyte.", "current_location_id": "loc_temple", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 50, "credulity": 75, "honesty": 60, "current_mood": "neutral"},
        {"id": "npc_10", "name": "Dorn", "archetype": "fisher", "faction": "dockers", "biography": "Harbor fisher.", "current_location_id": "loc_docks", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 60, "credulity": 60, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_11", "name": "Edda", "archetype": "bard", "faction": "free", "biography": "Traveling bard.", "current_location_id": "loc_tavern", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 88, "credulity": 42, "honesty": 52, "current_mood": "neutral"},
    ]


def _events() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"id": "event_1", "summary": "A fire damaged the south warehouse.", "severity": 70, "location_id": "loc_market", "occurred_at": now, "tick_id": 1, "participants": ["npc_1", "npc_7"], "event_type": "crime", "is_public": True},
        {"id": "event_2", "summary": "Bandits clashed with guards at the north gate.", "severity": 60, "location_id": "loc_keep", "occurred_at": now, "tick_id": 2, "participants": ["npc_2", "npc_8"], "event_type": "battle", "is_public": True},
        {"id": "event_3", "summary": "A rare relic was discovered near the temple.", "severity": 50, "location_id": "loc_temple", "occurred_at": now, "tick_id": 3, "participants": ["npc_3", "npc_9"], "event_type": "discovery", "is_public": True},
    ]


def _event_participation(events: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for event in events:
        for participant in event["participants"]:
            rows.append(
                {
                    "character_id": participant,
                    "event_id": event["id"],
                    "role": "witness",
                }
            )
    return rows


def _event_knowledge(events: list[dict], characters: list[dict]) -> list[dict]:
    rows: list[dict] = []
    non_player_ids = [item["id"] for item in characters if not item["is_player"]]
    for event in events:
        for character_id in non_player_ids:
            rows.append(
                {
                    "character_id": character_id,
                    "event_id": event["id"],
                    "knowledge_state": "knows",
                    "learned_at_tick": event["tick_id"],
                    "distortion_type": None,
                    "distortion_level": None,
                    "distorted_summary": None,
                    "source_character_id": None,
                }
            )
    return rows


async def seed() -> None:
    """Seed core world entities idempotently."""

    settings = get_settings()
    graph_db = GraphDB(settings=settings)
    await graph_db.connect()
    try:
        async with graph_db.get_session() as session:
            tx = await session.begin_transaction()
            async with tx:
                await tx.run(CYPHER_SEED_LOCATIONS, locations=_locations())
                characters = _characters()
                await tx.run(CYPHER_SEED_CHARACTERS, characters=characters)
                location_pairs = [
                    {
                        "character_id": character["id"],
                        "location_id": character["current_location_id"],
                        "is_permanent_resident": not character["is_player"],
                    }
                    for character in characters
                ]
                await tx.run(CYPHER_SEED_LOCATED_AT, pairs=location_pairs)
                await tx.run(CYPHER_SEED_WORLD)
                await tx.run(CYPHER_SEED_RELATIONS)
                events = _events()
                await tx.run(CYPHER_SEED_EVENTS, events=events)
                await tx.run(CYPHER_SEED_PARTICIPATION, participation=_event_participation(events))
                await tx.run(CYPHER_SEED_KNOWLEDGE, knowledge=_event_knowledge(events, characters))
                await tx.commit()
    finally:
        await graph_db.close()


if __name__ == "__main__":
    asyncio.run(seed())
