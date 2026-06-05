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


def _flatten_event_row(event_row: dict) -> dict:
    """Merge edge properties into event dict; isolate distorted account when present.

    The graph reader returns KNOWS_ABOUT edge fields (knowledge_state, distorted_summary)
    as siblings of the nested event dict. When distorted_summary is present the NPC has a
    personal (possibly wrong) account — returning ONLY that field prevents knowledge_state
    ("rumor") and other metadata from giving the LLM competing signals that cause hedging
    or reversion to ground-truth content.

    Args:
        event_row: Raw row from get_events_for_npc with keys "event", "knowledge_state",
            and "distorted_summary".

    Returns:
        Flat dict suitable for serialization into the LLM context.
    """
    distorted = event_row.get("distorted_summary")
    if distorted:
        return {"distorted_summary": distorted}
    flat = dict(event_row.get("event") or {})
    knowledge_state = event_row.get("knowledge_state")
    if knowledge_state is not None:
        flat["knowledge_state"] = knowledge_state
    return flat


def assemble_tier_a_context(
    *,
    npc_id: str,
    character_bundle: dict,
    events: list[dict],
    location_id: str | None,
    location_context: dict | None,
    group_memberships: list[dict] | None = None,
    believed_rumors: list[dict] | None = None,
    traits: list[dict] | None = None,
    active_pledges: list[dict] | None = None,
) -> list[ContextItem]:
    """Assemble Tier A ContextItems from pre-fetched graph data. Pure — no I/O.

    Args:
        npc_id: ID of the NPC to build context for.
        character_bundle: Pre-fetched character bundle (character + relations).
        events: Pre-fetched recent events the NPC knows about.
        location_id: The NPC's current location ID, or None if unknown.
        location_context: Pre-fetched location dict (location + present_npcs), or None.
        group_memberships: Optional list of group membership dicts from group_service.
        believed_rumors: Optional list of rumor belief dicts from rumor_service.
        traits: Optional list of trait dicts ordered by intensity; top 5 included.
        active_pledges: Optional list of active pledge dicts from pledge_service.

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
                pinned=True,
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

    top_traits = sorted(traits or [], key=lambda t: t.get("intensity", 0), reverse=True)[:5]
    if top_traits:
        items.append(
            ContextItem(
                key="traits",
                text=serialize_json(
                    [
                        {
                            "name": t.get("name"),
                            "intensity": t.get("intensity"),
                            "is_secret": t.get("is_secret"),
                        }
                        for t in top_traits
                    ]
                ),
                tier="tierA",
                priority=83,
            )
        )

    if group_memberships:
        items.append(
            ContextItem(
                key="group_memberships",
                text=serialize_json(
                    [
                        {
                            "type": "group",
                            "name": m.get("name"),
                            "kind": m.get("kind"),
                            "cohesion": m.get("cohesion"),
                            "role": m.get("role"),
                        }
                        for m in group_memberships
                    ]
                ),
                tier="tierA",
                priority=82,
            )
        )

    top_rumors = sorted(believed_rumors or [], key=lambda r: r.get("confidence", 0), reverse=True)[:3]
    if top_rumors:
        items.append(
            ContextItem(
                key="believed_rumors",
                text=serialize_json(
                    [
                        {
                            "type": "rumor",
                            "content": r.get("content"),
                            "confidence": r.get("confidence"),
                            "mutation_distance": r.get("mutation_distance"),
                        }
                        for r in top_rumors
                    ]
                ),
                tier="tierA",
                priority=81,
            )
        )

    active_pledge_list = [p for p in (active_pledges or []) if p.get("is_active")]
    if active_pledge_list:
        items.append(
            ContextItem(
                key="active_pledges",
                text=serialize_json(
                    [
                        {
                            "type": "pledge",
                            "pledgee_id": p.get("pledgee_id"),
                            "pledgee_name": p.get("pledgee_name"),
                            "pledge_type": p.get("pledge_type"),
                            "severity": p.get("severity"),
                            "expires_at_tick": p.get("expires_at_tick"),
                        }
                        for p in active_pledge_list
                    ]
                ),
                tier="tierA",
                priority=79,
            )
        )

    for index, event_row in enumerate(events):
        items.append(
            ContextItem(
                key=f"event:{index}:{npc_id}",
                text=serialize_json(
                    _flatten_event_row(event_row),
                    strip_nulls=True,
                    strip_fields=_LOW_VALUE_FIELDS,
                ),
                tier="tierA",
                priority=89 - index,
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
