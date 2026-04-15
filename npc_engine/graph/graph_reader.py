"""
graph_reader.py - Read-only Cypher accessors for NPC graph queries.

Does NOT: apply mutations or open transactions.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession
from typing import cast


CYPHER_GET_CHARACTER_WITH_RELATIONS = """
MATCH (c:Character {id: $npc_id})
OPTIONAL MATCH (c)-[r:RELATES_TO]->(other:Character)
RETURN properties(c) AS character,
       collect({relation: properties(r), character: properties(other)}) AS relations
"""

CYPHER_GET_EVENTS_FOR_NPC = """
MATCH (c:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event)
RETURN properties(e) AS event,
       k.knowledge_state AS knowledge_state,
       k.distorted_summary AS distorted_summary
ORDER BY e.occurred_at DESC
LIMIT $limit
"""

CYPHER_GET_LOCATION_CONTEXT = """
MATCH (loc:Location {id: $location_id})
OPTIONAL MATCH (c:Character)-[:LOCATED_AT]->(loc)
RETURN properties(loc) AS location, collect(properties(c)) AS present_npcs
"""

CYPHER_GET_NPC_PLAYER_EDGE = """
MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(p:Character {id: $player_id})
RETURN properties(r) AS relation
"""


async def get_character_with_relations(session: AsyncSession, npc_id: str) -> dict:
    """Fetch character node and directed outgoing relations."""

    result = await session.run(CYPHER_GET_CHARACTER_WITH_RELATIONS, npc_id=npc_id)
    record = await result.single()
    if record is None:
        return {"character": None, "relations": []}
    return {"character": record["character"], "relations": record["relations"]}


async def get_events_for_npc(session: AsyncSession, npc_id: str, limit: int = 10) -> list[dict]:
    """Fetch event knowledge entries for one NPC."""

    result = await session.run(CYPHER_GET_EVENTS_FOR_NPC, npc_id=npc_id, limit=limit)
    return [record.data() async for record in result]


async def get_location_context(session: AsyncSession, location_id: str) -> dict:
    """Fetch location details and currently present characters."""

    result = await session.run(CYPHER_GET_LOCATION_CONTEXT, location_id=location_id)
    record = await result.single()
    if record is None:
        return {"location": None, "present_npcs": []}
    return {"location": record["location"], "present_npcs": record["present_npcs"]}


async def get_npc_player_edge(session: AsyncSession, npc_id: str, player_id: str) -> dict | None:
    """Fetch directed relation edge from NPC to player."""

    result = await session.run(CYPHER_GET_NPC_PLAYER_EDGE, npc_id=npc_id, player_id=player_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict, record["relation"])
