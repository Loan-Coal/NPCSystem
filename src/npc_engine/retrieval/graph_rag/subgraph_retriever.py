"""
Module: subgraph_retriever
Layer: retrieval
Purpose: Assembles authoritative Tier A graph context items for an NPC from pre-fetched data.
Does NOT: query vector stores, serialize final prompt text, or touch Neo4j -- every
          function here is pure assembly over data the caller already fetched.
Dependencies injected: None.
Used by: retrieval.context_builder
"""

from __future__ import annotations

from typing import Any

from npc_engine.retrieval.context.context_merger import ContextItem
from npc_engine.retrieval.context.context_utils import (
    NON_PROMPT_NODE_FIELDS,
    serialize_json,
    _LOW_VALUE_FIELDS,
)

_NPC_NEARBY_FIELDS = ("id", "name", "archetype", "faction")

_EVENT_STRIP_FIELDS: frozenset[str] = _LOW_VALUE_FIELDS | NON_PROMPT_NODE_FIELDS
"""Events need both sets: the low-value ids the prompt cannot use, and the graph
bookkeeping every `properties(n)` payload drags in. Events previously got only the
first, so `embedding` and the wall-clock timestamps survived into the prompt."""


def _flatten_event_row(event_row: dict[str, Any]) -> dict[str, Any]:
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
        Flat dict[str, Any] suitable for serialization into the LLM context.
    """
    distorted = event_row.get("distorted_summary")
    knowledge_state = event_row.get("knowledge_state")
    if distorted:
        account: dict[str, Any] = {"distorted_summary": distorted}
        if knowledge_state is not None:
            account["knowledge_state"] = knowledge_state
        return account
    flat = dict(event_row.get("event") or {})
    if knowledge_state is not None:
        flat["knowledge_state"] = knowledge_state
    return flat


def _character_item(npc_id: str, character_payload: dict[str, Any] | None) -> list[ContextItem]:
    """Return character profile ContextItem, or [] if payload is absent.

    Strips NON_PROMPT_NODE_FIELDS: graph readers return `properties(c)` wholesale, which
    includes the 384-float `embedding` vector. Measured unstripped at 2,014 tokens —
    3.9x the entire prompt budget — inside this single pinned item (RET-P0.5).
    """
    if character_payload is None:
        return []
    return [
        ContextItem(
            key=f"character:{npc_id}",
            text=serialize_json(character_payload, strip_fields=NON_PROMPT_NODE_FIELDS),
            tier="tierA",
            priority=100,
            pinned=True,
        )
    ]


def _relation_item(relation_entries: list[dict[str, Any]]) -> list[ContextItem]:
    """Return player-relation ContextItem if the NPC has a relation with the player.

    ISSUE-070: EXP-11 in context_builder also emits key='relation:player' (priority=88).
    merge_context dedups by key keeping the higher priority, so priority=95 here wins
    deterministically — distinct priorities, no insertion-order ambiguity.
    """
    for entry in relation_entries:
        if entry.get("character", {}).get("is_player", False):
            relation = entry.get("relation", {})
            if relation:
                return [ContextItem(key="relation:player", text=serialize_json(relation, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=95)]
    return []


def _location_items(npc_id: str, character_payload: dict[str, Any] | None, location_id: str | None, location_context: dict[str, Any] | None) -> list[ContextItem]:
    """Return location + nearby-NPC ContextItems when the NPC's location is known."""
    if not (isinstance(character_payload, dict) and isinstance(location_id, str) and location_id != "" and location_context is not None):
        return []
    nearby_npcs = [
        {k: npc[k] for k in _NPC_NEARBY_FIELDS if k in npc}
        for npc in location_context.get("present_npcs", [])
        if isinstance(npc, dict) and npc.get("id") != npc_id and not npc.get("is_player", False)
    ]
    return [
        ContextItem(key=f"location:{location_id}", text=serialize_json(location_context.get("location", {}), strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=92),
        ContextItem(key="nearby_npcs", text=serialize_json(nearby_npcs), tier="tierA", priority=91),
    ]


def _trait_item(traits: list[dict[str, Any]] | None) -> list[ContextItem]:
    """Return top-5 trait ContextItem, or [] if no traits provided."""
    top = sorted(traits or [], key=lambda t: t.get("intensity", 0), reverse=True)[:5]
    if not top:
        return []
    return [ContextItem(key="traits", text=serialize_json([{"name": t.get("name"), "intensity": t.get("intensity"), "is_secret": t.get("is_secret")} for t in top], strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=83)]


def _group_item(group_memberships: list[dict[str, Any]] | None) -> list[ContextItem]:
    """Return group-memberships ContextItem, or [] if none provided."""
    if not group_memberships:
        return []
    return [ContextItem(key="group_memberships", text=serialize_json([{"type": "group", "name": m.get("name"), "kind": m.get("kind"), "cohesion": m.get("cohesion"), "role": m.get("role")} for m in group_memberships], strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=82)]


def _rumor_item(believed_rumors: list[dict[str, Any]] | None) -> list[ContextItem]:
    """Return top-3 rumor ContextItem, or [] if no rumors provided."""
    top = sorted(believed_rumors or [], key=lambda r: r.get("confidence", 0), reverse=True)[:3]
    if not top:
        return []
    return [ContextItem(key="believed_rumors", text=serialize_json([{"type": "rumor", "content": r.get("content"), "confidence": r.get("confidence"), "mutation_distance": r.get("mutation_distance")} for r in top], strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=81)]


def _pledge_item(active_pledges: list[dict[str, Any]] | None) -> list[ContextItem]:
    """Return active-pledges ContextItem, or [] if no active pledges.

    `expires_at_tick` is projected here but then removed by NON_PROMPT_NODE_FIELDS, which
    is deliberate: the deny-list is global and a per-producer exception is the kind of
    thing nobody remembers. It costs nothing observable today -- `active_pledges` has no
    slot in the serialized skeleton (ISSUE-200), so the item is assembled, ranked, charged
    to the tier-A budget and then discarded. When P5 gives it a slot, whether a bare tick
    number means anything to the model is a prompt-schema question, decided there.
    """
    active = [p for p in (active_pledges or []) if p.get("is_active")]
    if not active:
        return []
    return [ContextItem(key="active_pledges", text=serialize_json([{"type": "pledge", "pledgee_id": p.get("pledgee_id"), "pledgee_name": p.get("pledgee_name"), "pledge_type": p.get("pledge_type"), "severity": p.get("severity"), "expires_at_tick": p.get("expires_at_tick")} for p in active], strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=79)]


def _event_items(npc_id: str, events: list[dict[str, Any]]) -> list[ContextItem]:
    """Return one ContextItem per event the NPC knows about, priority-ranked by recency."""
    return [
        ContextItem(key=f"event:{i}:{npc_id}", text=serialize_json(_flatten_event_row(row), strip_nulls=True, strip_fields=_EVENT_STRIP_FIELDS), tier="tierA", priority=89 - i)
        for i, row in enumerate(events)
    ]


def assemble_tier_a_context(
    *,
    npc_id: str,
    character_bundle: dict[str, Any],
    events: list[dict[str, Any]],
    location_id: str | None,
    location_context: dict[str, Any] | None,
    group_memberships: list[dict[str, Any]] | None = None,
    believed_rumors: list[dict[str, Any]] | None = None,
    traits: list[dict[str, Any]] | None = None,
    active_pledges: list[dict[str, Any]] | None = None,
) -> list[ContextItem]:
    """Assemble Tier A ContextItems from pre-fetched graph data. Pure — no I/O.

    Args:
        npc_id: ID of the NPC to build context for.
        character_bundle: Pre-fetched character bundle (character + relations).
        events: Pre-fetched recent events the NPC knows about.
        location_id: The NPC's current location ID, or None if unknown.
        location_context: Pre-fetched location dict[str, Any] (location + present_npcs), or None.
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
