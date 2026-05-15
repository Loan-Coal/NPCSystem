"""
Module: subgraph_retriever
Layer: retrieval
Purpose: Assembles authoritative Tier A graph context items for an NPC from pre-fetched data.
Does NOT: query vector stores or serialize final prompt text.
Dependencies injected: AsyncSession (only in the legacy retrieve_tier_a_context wrapper).
Used by: retrieval.context_builder
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.graph_reader import get_character_with_relations, get_events_for_npc, get_location_context, get_npc_location_id
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_utils import serialize_json, _LOW_VALUE_FIELDS

_NPC_NEARBY_FIELDS = ("id", "name", "archetype", "faction")


def assemble_tier_a_context(
    *,
    npc_id: str,
    character_bundle: dict,
    events: list[dict],
    location_id: str | None,
    location_context: dict | None,
) -> list[ContextItem]:
    """Assemble Tier A ContextItems from pre-fetched graph data. Pure — no I/O.

    Args:
        npc_id: ID of the NPC to build context for.
        character_bundle: Pre-fetched character bundle (character + relations).
        events: Pre-fetched recent events the NPC knows about.
        location_id: The NPC's current location ID, or None if unknown.
        location_context: Pre-fetched location dict (location + present_npcs), or None.

    Returns:
        List of ContextItem values for tier A, ordered by priority descending.
    """

    items: list[ContextItem] = []
    relation_entries = character_bundle.get("relations", [])
    character_payload = character_bundle.get("character")

    if character_payload is not None:
        items.append(
            ContextItem(
                key=f"character:{npc_id}",
                text=serialize_json(character_payload),
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

    if isinstance(character_payload, dict) and isinstance(location_id, str) and location_id != "" and location_context is not None:
        items.append(
            ContextItem(
                key=f"location:{location_id}",
                text=serialize_json(location_context.get("location", {})),
                tier="tierA",
                priority=92,
            )
        )
        nearby_npcs = [
            {k: npc[k] for k in _NPC_NEARBY_FIELDS if k in npc}
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
                text=serialize_json(event, strip_nulls=True, strip_fields=_LOW_VALUE_FIELDS),
                tier="tierA",
                priority=80 - index,
            )
        )
    return items


async def retrieve_tier_a_context(
    session: AsyncSession,
    npc_id: str,
    event_limit: int,
    character_bundle: dict | None = None,
) -> list[ContextItem]:
    """Fetch graph-backed tier A context items for an NPC.

    Retrieves character profile, player relation, location context, nearby NPCs,
    and recent events from the graph. Delegates assembly to assemble_tier_a_context.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC to build context for.
        event_limit: Maximum number of recent events to include.
        character_bundle: Pre-fetched character bundle; avoids a second graph round-trip
            when the caller already fetched it for cache-key computation.

    Returns:
        List of ContextItem values for tier A, ordered by priority descending.
    """

    bundle = character_bundle if character_bundle is not None else (
        await get_character_with_relations(session=session, npc_id=npc_id)
    )
    events = await get_events_for_npc(session=session, npc_id=npc_id, limit=event_limit)

    character_payload = bundle.get("character")
    location_id: str | None = None
    location_context: dict | None = None
    if isinstance(character_payload, dict):
        location_id = await get_npc_location_id(session=session, npc_id=npc_id)
        if isinstance(location_id, str) and location_id != "":
            location_context = await get_location_context(session=session, location_id=location_id)

    return assemble_tier_a_context(
        npc_id=npc_id,
        character_bundle=bundle,
        events=events,
        location_id=location_id,
        location_context=location_context,
    )
