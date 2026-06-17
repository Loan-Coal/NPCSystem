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
    personal (possibly wrong) account — we surface ONLY that account and suppress the
    competing ground-truth summary (to keep the gossip-distortion content, not revert to
    ground truth). We retain knowledge_state alongside it (S26.1, ISSUE-093) so the prompt
    can frame a rumour as hearsay rather than recasting it as a firsthand MY_ACCOUNT.

    Args:
        event_row: Raw row from get_events_for_npc with keys "event", "knowledge_state",
            and "distorted_summary".

    Returns:
        Flat dict suitable for serialization into the LLM context.
    """
    distorted = event_row.get("distorted_summary")
    knowledge_state = event_row.get("knowledge_state")
    if distorted:
        account: dict = {"distorted_summary": distorted}
        if knowledge_state is not None:
            account["knowledge_state"] = knowledge_state
        return account
    flat = dict(event_row.get("event") or {})
    if knowledge_state is not None:
        flat["knowledge_state"] = knowledge_state
    return flat


def _character_item(npc_id: str, character_payload: dict | None) -> list[ContextItem]:
    """Return character profile ContextItem, or [] if payload is absent."""
    if character_payload is None:
        return []
    return [ContextItem(key=f"character:{npc_id}", text=serialize_json(character_payload), tier="tierA", priority=100, pinned=True)]


def _relation_item(relation_entries: list[dict]) -> list[ContextItem]:
    """Return player-relation ContextItem if the NPC has a relation with the player.

    ISSUE-070: EXP-11 in context_builder also emits key='relation:player' (priority=88).
    merge_context dedups by key keeping the higher priority, so priority=95 here wins
    deterministically — distinct priorities, no insertion-order ambiguity.
    """
    for entry in relation_entries:
        if entry.get("character", {}).get("is_player", False):
            relation = entry.get("relation", {})
            if relation:
                return [ContextItem(key="relation:player", text=serialize_json(relation), tier="tierA", priority=95)]
    return []


def _location_items(npc_id: str, character_payload: dict | None, location_id: str | None, location_context: dict | None) -> list[ContextItem]:
    """Return location + nearby-NPC ContextItems when the NPC's location is known."""
    if not (isinstance(character_payload, dict) and isinstance(location_id, str) and location_id != "" and location_context is not None):
        return []
    nearby_npcs = [
        {k: npc[k] for k in _NPC_NEARBY_FIELDS if k in npc}
        for npc in location_context.get("present_npcs", [])
        if isinstance(npc, dict) and npc.get("id") != npc_id and not npc.get("is_player", False)
    ]
    return [
        ContextItem(key=f"location:{location_id}", text=serialize_json(location_context.get("location", {})), tier="tierA", priority=92),
        ContextItem(key="nearby_npcs", text=serialize_json(nearby_npcs), tier="tierA", priority=91),
    ]


def _trait_item(traits: list[dict] | None) -> list[ContextItem]:
    """Return top-5 trait ContextItem, or [] if no traits provided."""
    top = sorted(traits or [], key=lambda t: t.get("intensity", 0), reverse=True)[:5]
    if not top:
        return []
    return [ContextItem(key="traits", text=serialize_json([{"name": t.get("name"), "intensity": t.get("intensity"), "is_secret": t.get("is_secret")} for t in top]), tier="tierA", priority=83)]


def _group_item(group_memberships: list[dict] | None) -> list[ContextItem]:
    """Return group-memberships ContextItem, or [] if none provided."""
    if not group_memberships:
        return []
    return [ContextItem(key="group_memberships", text=serialize_json([{"type": "group", "name": m.get("name"), "kind": m.get("kind"), "cohesion": m.get("cohesion"), "role": m.get("role")} for m in group_memberships]), tier="tierA", priority=82)]


def _rumor_item(believed_rumors: list[dict] | None) -> list[ContextItem]:
    """Return top-3 rumor ContextItem, or [] if no rumors provided."""
    top = sorted(believed_rumors or [], key=lambda r: r.get("confidence", 0), reverse=True)[:3]
    if not top:
        return []
    return [ContextItem(key="believed_rumors", text=serialize_json([{"type": "rumor", "content": r.get("content"), "confidence": r.get("confidence"), "mutation_distance": r.get("mutation_distance")} for r in top]), tier="tierA", priority=81)]


def _pledge_item(active_pledges: list[dict] | None) -> list[ContextItem]:
    """Return active-pledges ContextItem, or [] if no active pledges."""
    active = [p for p in (active_pledges or []) if p.get("is_active")]
    if not active:
        return []
    return [ContextItem(key="active_pledges", text=serialize_json([{"type": "pledge", "pledgee_id": p.get("pledgee_id"), "pledgee_name": p.get("pledgee_name"), "pledge_type": p.get("pledge_type"), "severity": p.get("severity"), "expires_at_tick": p.get("expires_at_tick")} for p in active]), tier="tierA", priority=79)]


def _event_items(npc_id: str, events: list[dict]) -> list[ContextItem]:
    """Return one ContextItem per event the NPC knows about, priority-ranked by recency."""
    return [
        ContextItem(key=f"event:{i}:{npc_id}", text=serialize_json(_flatten_event_row(row), strip_nulls=True, strip_fields=_LOW_VALUE_FIELDS), tier="tierA", priority=89 - i)
        for i, row in enumerate(events)
    ]


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
    relation_entries = character_bundle.get("relations", [])
    character_payload = character_bundle.get("character")
    return [
        *_character_item(npc_id, character_payload),
        *_relation_item(relation_entries),
        *_location_items(npc_id, character_payload, location_id, location_context),
        *_trait_item(traits),
        *_group_item(group_memberships),
        *_rumor_item(believed_rumors),
        *_pledge_item(active_pledges),
        *_event_items(npc_id, events),
    ]


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
