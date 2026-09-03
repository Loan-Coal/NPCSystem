"""
Module: context_tier_builders
Layer: retrieval
Purpose: Turn raw graph and RAG reads into the tier-0, tier-A, tier-B and tier-C ContextItem lists.
Does NOT: read the graph, call an LLM, rank, budget or serialize - item construction only.
Dependencies: context_merger, context_slots, context_profile_policy, context_utils, context_builder_helpers.
Dependencies injected: Settings and RetrievalProfile are passed per call; no stateful collaborators.
Used by: retrieval.context.context_builder
"""

from __future__ import annotations

from typing import Any

from npc_engine.config import Settings
from npc_engine.retrieval.graph_rag.memory_temporal import annotate_memory_ages
from npc_engine.retrieval.graph_rag.subgraph_retriever import assemble_tier_a_context
from npc_engine.world.time_utils import TimePoint

from .context_builder_helpers import normalize_ratio, to_json_safe
from .context_merger import ContextItem
from .context_slots import slot_for_key
from .context_utils import NON_PROMPT_NODE_FIELDS, serialize_json


def _build_tier0_items(
    world_state: Any,
    emotion_snapshot: dict[str, Any],
    system_state_context: Any | None = None,
) -> list[ContextItem]:
    """Build pinned Tier 0 context items: world state, current emotion, and system state.

    Every item here is pinned into every prompt, so each is serialized through
    NON_PROMPT_NODE_FIELDS. These previously used raw model_dump_json(), which put
    `world.last_updated_at` — a wall-clock value — into every prompt the engine built
    (EVAL-P20.0 / DEC-176).

    Args:
        world_state: Authoritative world state from the graph.
        emotion_snapshot: Current NPC emotion snapshot dict.
        system_state_context: Optional engine-resolved SystemStateContext (ISSUE-071).
    """
    items = [
        _pinned_tier0_item(key="world", payload=world_state.model_dump(mode="json"), priority=100),
        _pinned_tier0_item(key="emotion", payload=emotion_snapshot, priority=95),
    ]
    if system_state_context is not None:
        items.append(
            _pinned_tier0_item(
                key="system_state",
                payload=system_state_context.model_dump(mode="json"),
                priority=97,
            )
        )
    return items
def _pinned_tier0_item(*, key: str, payload: Any, priority: int) -> ContextItem:
    """Serialize a Tier 0 payload with wall-clock fields stripped (DEC-176)."""
    return ContextItem(
        key=key,
        text=serialize_json(payload, strip_fields=NON_PROMPT_NODE_FIELDS),
        tier="tier0",
        priority=priority,
        pinned=True,
    )
def _build_tier_a_base(
    npc_id: str, character_bundle: dict[str, Any], events: list[Any], location_id: str | None,
    location_context: Any, group_memberships: list[Any], believed_rumors: list[Any],
    traits: list[Any], active_pledges: list[Any], session_turns: list[str],
) -> list[ContextItem]:
    """Build base Tier A items: session turns followed by NPC character profile section."""
    items = [ContextItem(key="session", text=serialize_json(session_turns), tier="tierA", priority=99, pinned=True)]
    items.extend(assemble_tier_a_context(
        npc_id=npc_id, character_bundle=character_bundle, events=events, location_id=location_id,
        location_context=location_context, group_memberships=group_memberships or [],
        believed_rumors=believed_rumors or [], traits=traits or [], active_pledges=active_pledges or [],
    ))
    return items
def _build_tier_a_extended(
    player_id: str | None, reputation_items: list[Any], active_quest: Any,
    player_relation_edge: dict[str, Any] | None,
    memories: list[Any], beliefs: list[Any], goals: list[Any], owned_items: list[Any],
    secrets: list[Any], obligations: list[Any],
    second_hop_events: list[Any], settings: Settings, npc_id: str, game_time: TimePoint | None = None,
    propagated_reputation: list[Any] | None = None,
) -> list[ContextItem]:
    """Build extended Tier A items: reputation, quest, beliefs, memories, second-hop events, etc."""
    items: list[Any] = []
    if player_id and reputation_items:
        items.append(ContextItem(key="reputation", text=serialize_json(reputation_items, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=85))
    # Ranks just below direct reputation on purpose: system_v1.yaml Rule 13 says to apply
    # word-of-mouth reputation ONLY where Rule 2's direct reputation has no entry.
    if player_id and propagated_reputation:
        items.append(ContextItem(key="propagated_reputation", text=serialize_json(propagated_reputation, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=84))
    if active_quest:
        items.append(ContextItem(key="active_quest", text=serialize_json(active_quest, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=89, pinned=True))
    if player_relation_edge is not None:
        # ISSUE-070: subgraph_retriever also emits key="relation:player" (priority=95). merge_context dedups
        # by key keeping the higher priority, so the subgraph item wins deterministically when both are
        # present; this 88 applies only when subgraph_retriever produced no relation edge.
        items.append(ContextItem(key="relation:player", text=serialize_json(player_relation_edge, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=88))
    if memories:
        aged_memories = annotate_memory_ages(memories, game_time)
        items.append(ContextItem(key="memories", text=serialize_json(aged_memories, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=90))
    if beliefs:
        items.append(ContextItem(key="beliefs", text=serialize_json(beliefs, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=88))
    if goals:
        items.append(ContextItem(key="goals", text=serialize_json(goals, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=87))
    if owned_items:
        items.append(ContextItem(key="owned_items", text=serialize_json(owned_items, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=86))
    if secrets:
        items.append(ContextItem(key="secrets", text=serialize_json(secrets, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=84))
    if obligations:
        items.append(ContextItem(key="obligations", text=serialize_json(obligations, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=83))
    for idx, evt in enumerate((second_hop_events or [])[:settings.MAX_SECOND_HOP_EVENTS]):
        items.append(ContextItem(key=f"second_hop:{idx}:{npc_id}", text=serialize_json(evt, strip_nulls=True, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=74 - idx))
    return items
def _build_tier_b_c_items(tier_b_results: list[Any]) -> tuple[Any, ...]:
    """Split RAG results into Tier B/C ContextItems and build a vector score map."""
    tier_b_raw: list[Any] = []
    tier_c_raw: list[Any] = []
    vector_scores: dict[str, float] = {}
    if not tier_b_results:
        return tier_b_raw, tier_c_raw, vector_scores
    split_index = max(1, len(tier_b_results) // 2)
    for index, row in enumerate(tier_b_results):
        item = ContextItem(
            key=f"rag:{row['id']}",
            text=serialize_json(to_json_safe(row["payload"]), strip_fields=NON_PROMPT_NODE_FIELDS),
            tier="tierB" if index < split_index else "tierC",
            priority=max(1, 60 - index),
        )
        (tier_b_raw if item.tier == "tierB" else tier_c_raw).append(item)
    vector_scores = {f"rag:{row['id']}": normalize_ratio(float(row.get("score", 0.0))) for row in tier_b_results}
    return tier_b_raw, tier_c_raw, vector_scores
def _build_event_trust_map(events: list[Any], trust_scores: dict[str, Any], npc_id: str) -> dict[str, float]:
    """Map event ContextItem keys (positional index) to their trust scores."""
    event_key_trust: dict[str, float] = {}
    for idx, evt in enumerate(events):
        eid = str(evt.get("id", ""))
        if eid in trust_scores:
            event_key_trust[f"event:{idx}:{npc_id}"] = trust_scores[eid]
    return event_key_trust
def _drop_withheld_items(items: list[ContextItem]) -> list[ContextItem]:
    """Remove items whose declared slot the serializer will not emit.

    ISSUE-200's cost was not the missing serializer lines, it was that the keys were
    produced, ranked and CHARGED to the prompt budget before being discarded -- roughly
    110 tokens a turn bought and never delivered, while items that would have reached the
    model were dropped for want of room.

    Central on purpose. There are four producer modules and twenty-odd call sites; a check
    inside each producer is what gets forgotten at the twenty-first, which is how ISSUE-200
    happened in the first place.

    Fails OPEN: a key no slot declares is kept, because dropping it would hide in production
    exactly the defect `test_context_slot_contract` exists to surface in CI.

    Args:
        items: Raw context items from the producers, in production order.
    Returns:
        The same items, in the same order, minus those whose slot is withheld.
    """
    kept: list[ContextItem] = []
    for item in items:
        slot = slot_for_key(item.key)
        if slot is not None and not slot.default_enabled:
            continue
        kept.append(item)
    return kept
