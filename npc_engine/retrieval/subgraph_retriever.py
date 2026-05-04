"""
subgraph_retriever.py - Retrieves authoritative Tier A graph context for an NPC.

Does NOT: query vector stores or serialize final prompt text.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession

from graph.graph_reader import get_character_with_relations, get_events_for_npc, get_location_context, get_npc_location_id
from retrieval.context_merger import ContextItem
from retrieval.context_utils import serialize_json


async def retrieve_tier_a_context(session: AsyncSession, npc_id: str, event_limit: int) -> list[ContextItem]:
    """Fetch graph-backed tier A context items for an NPC.

    Retrieves character profile, player relation, location context, nearby NPCs,
    and recent events from the graph.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC to build context for.
        event_limit: Maximum number of recent events to include.

    Returns:
        List of ContextItem values for tier A, ordered by priority descending.
    """

    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    events = await get_events_for_npc(session=session, npc_id=npc_id, limit=event_limit)

    items: list[ContextItem] = []
    relation_entries = character_bundle.get("relations", [])
    character_payload = character_bundle.get("character")

    if character_bundle.get("character") is not None:
        items.append(
            ContextItem(
                key=f"character:{npc_id}",
                text=serialize_json(character_bundle["character"]),
                tier="tierA",
                priority=100,
            )
        )

    player_relation = {}
    for relation_entry in relation_entries:
        character = relation_entry.get("character", {})
        if character.get("is_player", False):
            player_relation = relation_entry.get("relation", {})
            break
    if len(player_relation) > 0:
        items.append(
            ContextItem(
                key="relation:player",
                text=serialize_json(player_relation),
                tier="tierA",
                priority=95,
            )
        )

    if isinstance(character_payload, dict):
        location_id = await get_npc_location_id(session=session, npc_id=npc_id)
        if isinstance(location_id, str) and location_id != "":
            location_context = await get_location_context(session=session, location_id=location_id)
            items.append(
                ContextItem(
                    key=f"location:{location_id}",
                    text=serialize_json(location_context.get("location", {})),
                    tier="tierA",
                    priority=92,
                )
            )
            nearby_npcs = [
                npc
                for npc in location_context.get("present_npcs", [])
                if isinstance(npc, dict)
                and npc.get("id") != npc_id
                and not npc.get("is_player", False)
            ]
            items.append(
                ContextItem(
                    key="nearby_npcs",
                    text=serialize_json(nearby_npcs),
                    tier="tierA",
                    priority=91,
                )
            )

    for index, event in enumerate(events):
        items.append(
            ContextItem(
                key=f"event:{index}:{npc_id}",
                text=serialize_json(event),
                tier="tierA",
                priority=80 - index,
            )
        )
    return items
