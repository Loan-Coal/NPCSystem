"""
seed.py - Idempotent seed routines for locations, characters, relations, events, and world state.

Does NOT: run API server lifecycle or scheduler ticks.

Dependencies injected: Settings.
"""

import asyncio
from datetime import datetime, timezone

from graph.db import GraphDB
from config import get_settings
from data.seed_queries import (
    CYPHER_SEED_CHARACTERS,
    CYPHER_SEED_EVENTS,
    CYPHER_SEED_KNOWLEDGE,
    CYPHER_SEED_LOCATED_AT,
    CYPHER_SEED_LOCATIONS,
    CYPHER_SEED_PARTICIPATION,
    CYPHER_SEED_RELATIONS,
    CYPHER_SEED_WORLD,
)


CHARACTER_LOCATION_MAP: dict[str, str] = {
    "player_1": "loc_market",
    "npc_1": "loc_market",
    "npc_2": "loc_keep",
    "npc_3": "loc_temple",
    "npc_4": "loc_docks",
    "npc_5": "loc_tavern",
    "npc_6": "loc_market",
    "npc_7": "loc_market",
    "npc_8": "loc_keep",
    "npc_9": "loc_temple",
    "npc_10": "loc_docks",
    "npc_11": "loc_tavern",
}

EVENT_PARTICIPATION: list[dict[str, str]] = [
    {"character_id": "npc_1", "event_id": "event_1", "role": "witness"},
    {"character_id": "npc_7", "event_id": "event_1", "role": "witness"},
    {"character_id": "npc_2", "event_id": "event_2", "role": "witness"},
    {"character_id": "npc_8", "event_id": "event_2", "role": "witness"},
    {"character_id": "npc_3", "event_id": "event_3", "role": "witness"},
    {"character_id": "npc_9", "event_id": "event_3", "role": "witness"},
]


def _locations() -> list[dict]:
    """Return static seed location definitions.

    Returns:
        List of location property dicts for MERGE into the graph.
    """
    return [
        {"id": "loc_tavern", "name": "Iron Lantern", "region": "North", "location_tag": "tavern", "descriptor": "A busy tavern."},
        {"id": "loc_market", "name": "Grand Market", "region": "Central", "location_tag": "market", "descriptor": "Crowded stalls."},
        {"id": "loc_keep", "name": "Stone Keep", "region": "Central", "location_tag": "keep", "descriptor": "Fortified keep."},
        {"id": "loc_docks", "name": "Salt Docks", "region": "South", "location_tag": "docks", "descriptor": "Trading harbor."},
        {"id": "loc_temple", "name": "Sun Temple", "region": "East", "location_tag": "temple", "descriptor": "Quiet sanctuary."},
    ]


def _characters() -> list[dict]:
    """Return static seed character definitions with a consistent timestamp.

    Returns:
        List of character property dicts for MERGE into the graph.
    """
    base_time = datetime.now(timezone.utc).isoformat()
    return [
        {"id": "player_1", "name": "Player", "archetype": "adventurer", "faction": "free", "biography": "A wandering player.", "is_player": True, "created_at": base_time, "updated_at": base_time, "gossipy": 50, "credulity": 50, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_1", "name": "Aldric", "archetype": "merchant", "faction": "guild", "biography": "Veteran merchant.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 70, "credulity": 45, "honesty": 65, "current_mood": "neutral"},
        {"id": "npc_2", "name": "Sera", "archetype": "guard", "faction": "guard", "biography": "City guard captain.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 30, "credulity": 35, "honesty": 80, "current_mood": "neutral"},
        {"id": "npc_3", "name": "Mira", "archetype": "healer", "faction": "temple", "biography": "Temple healer.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 45, "credulity": 65, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_4", "name": "Garr", "archetype": "sailor", "faction": "dockers", "biography": "Dock foreman.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 80, "credulity": 55, "honesty": 40, "current_mood": "neutral"},
        {"id": "npc_5", "name": "Lenna", "archetype": "barkeep", "faction": "free", "biography": "Runs the tavern.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 85, "credulity": 50, "honesty": 55, "current_mood": "neutral"},
        {"id": "npc_6", "name": "Ivor", "archetype": "scribe", "faction": "guild", "biography": "Guild record keeper.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 35, "credulity": 40, "honesty": 70, "current_mood": "neutral"},
        {"id": "npc_7", "name": "Rook", "archetype": "thief", "faction": "free", "biography": "Streetwise pickpocket.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 90, "credulity": 45, "honesty": 25, "current_mood": "neutral"},
        {"id": "npc_8", "name": "Bran", "archetype": "guard", "faction": "guard", "biography": "Gate sentry.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 25, "credulity": 40, "honesty": 75, "current_mood": "neutral"},
        {"id": "npc_9", "name": "Thalia", "archetype": "acolyte", "faction": "temple", "biography": "Young acolyte.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 50, "credulity": 75, "honesty": 60, "current_mood": "neutral"},
        {"id": "npc_10", "name": "Dorn", "archetype": "fisher", "faction": "dockers", "biography": "Harbor fisher.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 60, "credulity": 60, "honesty": 50, "current_mood": "neutral"},
        {"id": "npc_11", "name": "Edda", "archetype": "bard", "faction": "free", "biography": "Traveling bard.", "is_player": False, "created_at": base_time, "updated_at": base_time, "gossipy": 88, "credulity": 42, "honesty": 52, "current_mood": "neutral"},
    ]


def _events() -> list[dict]:
    """Return static seed event definitions with a current timestamp.

    Returns:
        List of event property dicts for MERGE into the graph.
    """
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"id": "event_1", "summary": "A fire damaged the south warehouse.", "severity": 70, "location_id": "loc_market", "occurred_at": now, "tick_id": 1, "event_type": "crime", "is_public": True},
        {"id": "event_2", "summary": "Bandits clashed with guards at the north gate.", "severity": 60, "location_id": "loc_keep", "occurred_at": now, "tick_id": 2, "event_type": "battle", "is_public": True},
        {"id": "event_3", "summary": "A rare relic was discovered near the temple.", "severity": 50, "location_id": "loc_temple", "occurred_at": now, "tick_id": 3, "event_type": "discovery", "is_public": True},
    ]


def _event_knowledge(events: list[dict], characters: list[dict]) -> list[dict]:
    """Build KNOWS_ABOUT relationship rows for all non-player characters and events.

    Args:
        events: List of event dicts from _events().
        characters: List of character dicts from _characters().

    Returns:
        List of knowledge rows for MERGE into KNOWS_ABOUT edges.
    """
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
    """Seed core world entities idempotently.

    Returns:
        None. All writes are committed in a single transaction.
    """
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
                        "location_id": CHARACTER_LOCATION_MAP[character["id"]],
                        "is_permanent_resident": not character["is_player"],
                    }
                    for character in characters
                ]
                await tx.run(CYPHER_SEED_LOCATED_AT, pairs=location_pairs)
                await tx.run(CYPHER_SEED_WORLD)
                await tx.run(CYPHER_SEED_RELATIONS)
                events = _events()
                await tx.run(CYPHER_SEED_EVENTS, events=events)
                await tx.run(CYPHER_SEED_PARTICIPATION, participation=EVENT_PARTICIPATION)
                await tx.run(CYPHER_SEED_KNOWLEDGE, knowledge=_event_knowledge(events, characters))
                await tx.commit()
    finally:
        await graph_db.close()


if __name__ == "__main__":
    asyncio.run(seed())
