"""
graph_reader.py - Read-only Cypher accessors for NPC graph queries.

Does NOT: apply mutations or open transactions.

Dependencies injected: AsyncSession.
"""

from datetime import datetime
from typing import Any, cast

from neo4j import AsyncSession


CYPHER_GET_CHARACTER_WITH_RELATIONS = """
MATCH (c:Character {id: $npc_id})
WHERE c.is_active = true
OPTIONAL MATCH (c)-[r:RELATES_TO]->(other:Character)
WHERE other.is_active = true
RETURN properties(c) AS character,
       collect({relation: properties(r), character: properties(other)}) AS relations
"""

CYPHER_GET_EVENTS_FOR_NPC = """
MATCH (c:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event)
WHERE c.is_active = true
RETURN properties(e) AS event,
       k.knowledge_state AS knowledge_state,
       k.distorted_summary AS distorted_summary
ORDER BY e.occurred_at DESC
LIMIT $limit
"""

CYPHER_GET_LOCATION_CONTEXT = """
MATCH (loc:Location {id: $location_id})
OPTIONAL MATCH (c:Character)-[:LOCATED_AT]->(loc)
WHERE c.is_active = true
RETURN properties(loc) AS location, collect(properties(c)) AS present_npcs
"""

CYPHER_GET_NPC_LOCATION_ID = """
MATCH (c:Character {id: $npc_id})-[:LOCATED_AT]->(loc:Location)
WHERE c.is_active = true
RETURN loc.id AS location_id
"""

CYPHER_GET_NPC_PLAYER_EDGE = """
MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(p:Character {id: $player_id})
WHERE npc.is_active = true
RETURN properties(r) AS relation
"""

CYPHER_GET_KNOWN_EVENT_IDS = """
MATCH (c:Character {id: $npc_id})-[:KNOWS_ABOUT]->(e:Event)
WHERE c.is_active = true
RETURN e.id AS id
"""


async def get_character_with_relations(session: AsyncSession, npc_id: str) -> dict[str, Any]:
    """Fetch character node and directed outgoing relations.

    Args:
        session: Active Neo4j async session for the read query.
        npc_id: ID of the character node to fetch.

    Returns:
        Dict with "character" (node properties or None) and "relations" (list of
        active outgoing RELATES_TO dicts, omitting entries with null character nodes).
    """

    result = await session.run(CYPHER_GET_CHARACTER_WITH_RELATIONS, npc_id=npc_id)
    record = await result.single()
    if record is None:
        return {"character": None, "relations": []}
    normalized_relations_raw = _to_native(record["relations"])
    normalized_relations = []
    if isinstance(normalized_relations_raw, list):
        for item in normalized_relations_raw:
            if not isinstance(item, dict):
                continue
            if not isinstance(item.get("character"), dict):
                continue
            normalized_relations.append(item)

    return {
        "character": _to_native(record["character"]),
        "relations": normalized_relations,
    }


async def get_events_for_npc(session: AsyncSession, npc_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch event knowledge entries for one NPC.

    Args:
        session: Active Neo4j async session for the read query.
        npc_id: ID of the character node whose event knowledge is fetched.
        limit: Maximum number of events to return, ordered by most-recent first.

    Returns:
        List of dicts containing event properties, knowledge_state, and distorted_summary.
    """

    result = await session.run(CYPHER_GET_EVENTS_FOR_NPC, npc_id=npc_id, limit=limit)
    return cast(list[dict], [_to_native(record.data()) async for record in result])


async def get_location_context(session: AsyncSession, location_id: str) -> dict[str, Any]:
    """Fetch location details and currently present characters.

    Args:
        session: Active Neo4j async session for the read query.
        location_id: ID of the location node to fetch.

    Returns:
        Dict with "location" (node properties or None) and "present_npcs"
        (list of active character property dicts at that location).
    """

    result = await session.run(CYPHER_GET_LOCATION_CONTEXT, location_id=location_id)
    record = await result.single()
    if record is None:
        return {"location": None, "present_npcs": []}
    return {
        "location": _to_native(record["location"]),
        "present_npcs": _to_native(record["present_npcs"]),
    }


async def get_npc_location_id(session: AsyncSession, npc_id: str) -> str | None:
    """Fetch the current location id for an NPC via LOCATED_AT edge.

    Args:
        session: Active Neo4j async session for the read query.
        npc_id: ID of the active character node.

    Returns:
        Location node ID string, or None if the NPC has no LOCATED_AT edge.
    """

    result = await session.run(CYPHER_GET_NPC_LOCATION_ID, npc_id=npc_id)
    record = await result.single()
    if record is None:
        return None
    return cast(str, record["location_id"])


async def get_known_event_ids_for_npc(session: AsyncSession, npc_id: str) -> set[str]:
    """Return the set of Event IDs this NPC has KNOWS_ABOUT edges to.

    Args:
        session: Active Neo4j async session for the read query.
        npc_id: ID of the character node whose known events are fetched.

    Returns:
        Set of event ID strings the NPC knows about.
    """

    result = await session.run(CYPHER_GET_KNOWN_EVENT_IDS, npc_id=npc_id)
    return {str(record["id"]) async for record in result}


async def get_npc_player_edge(session: AsyncSession, npc_id: str, player_id: str) -> dict[str, Any] | None:
    """Fetch directed relation edge from NPC to player.

    Args:
        session: Active Neo4j async session for the read query.
        npc_id: ID of the source character node.
        player_id: ID of the target character node.

    Returns:
        Dict of RELATES_TO edge properties, or None if no such edge exists.
    """

    result = await session.run(CYPHER_GET_NPC_PLAYER_EDGE, npc_id=npc_id, player_id=player_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict, _to_native(record["relation"]))


def _to_native(value: Any) -> Any:
    """Recursively convert Neo4j values to native Python containers/scalars."""

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _to_native(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_native(item) for item in value]

    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        try:
            return _to_native(to_native())
        except Exception:
            return value

    return value
