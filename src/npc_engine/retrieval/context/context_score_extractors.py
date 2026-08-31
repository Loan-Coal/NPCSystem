"""
Module: context_score_extractors
Layer: retrieval
Purpose: Read the four relevance signals -- recency, severity, relation, quest -- and the
         proximity hop count, out of one context item's key and serialized payload.
Does NOT: rank, weight, combine, fetch, or serialize. Every function here answers one
          question about one item and returns a ratio in [0, 1].
Dependencies injected: none -- the declaration table is imported data, values are passed in.
Used by: retrieval.context.context_scoring (which combines these into a candidate).

Split out of context_scoring.py when that file passed the 300-line cap. The seam is real
rather than arbitrary: everything here is a pure function of (key, payload text), and
everything left behind orchestrates them into a ranked list.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from npc_engine.common.json_utils import parse_json_list, parse_json_object

from .context_merger import ContextItem
from .context_slots import (
    NPC_SELF_STATE_KEYS,
    SELF_STATE_PROXIMITY_HOPS,
    severity_field_for_key,
)
from npc_engine.world.time_utils import TimePoint, total_days

__all__ = [
    "payload_for_scoring",
    "extract_recency_score",
    "extract_relation_score",
    "extract_severity_score",
    "extract_severity_score_for_item",
    "infer_proximity_hops",
    "normalize_ratio",
    "quest_score",
]


# Which record represents an ARRAY payload.
#
# RECENCY is still scored on the FIRST record: every producer orders its rows by its own
# notion of importance, and where rerank_by_keyword has reordered beliefs, goals and secrets
# the first record is instead the one most relevant to the player's message. Either way it
# is a deliberate choice by something upstream.
#
# SEVERITY is no longer. It used to read the first record through a generic fallback chain,
# which was right only where the producer's ORDER BY happened to be the field the chain hit
# first -- true for beliefs (confidence), goals (urgency), secrets (severity) and
# believed_rumors (confidence), and false for memories (ordered by vividness, scored on
# emotional_charge) and active_pledges (ordered by sworn_at_tick, scored on severity). For
# those two the representative was merely the most vivid memory and the most recently sworn
# pledge. `context_slots` now names the field per slot and the scorer takes its MAXIMUM
# across records, which removes the dependency on producer ordering rather than documenting
# it. See ISSUE-206 and extract_severity_score_for_item.
def payload_for_scoring(text: str) -> dict[str, Any]:
    """Return the one record this item should be scored on, object- or array-shaped.

    Every item carrying an NPC's inner life is a JSON ARRAY of records -- `beliefs`, `goals`,
    `memories`, `secrets`, `obligations`, `owned_items`, `reputation`, `traits`,
    `believed_rumors`, `nearby_npcs`. `parse_json_object` returns {} for an array, so all of
    them scored recency 0.0 and severity 0.0 and were ranked on proximity and priority alone,
    and the four severity fallbacks below could not be reached by any input the engine
    actually produces. The comment above records which record is picked and why.

    Args:
        text: The item's serialized payload.
    Returns:
        The payload object, the first object in a payload array, or {} when the payload is
        neither (a list of strings, an empty list, or unparseable text).
    """
    payload = parse_json_object(text)
    if payload:
        return payload
    for row in parse_json_list(text):
        if isinstance(row, dict):
            return row
    return {}


def extract_recency_score(
    payload: dict[str, Any],
    *,
    game_time: TimePoint | None = None,
    game_day_horizon: int = 365,
) -> float:
    # Game-time nodes (Belief, Goal, Memory): score against current structured game time.
    raw_game_time = payload.get("created_at_game_time") or payload.get("occurred_at_game_time")
    if raw_game_time is not None and game_time is not None:
        try:
            gt = json.loads(raw_game_time) if isinstance(raw_game_time, str) else raw_game_time
            node_tp = TimePoint(
                year=int(gt.get("year", 0)),
                season=str(gt.get("season", "spring")),
                day=int(gt.get("day", 1)),
                time_of_day=str(gt.get("time_of_day", "morning")),
            )
            age_days = max(0, total_days(game_time) - total_days(node_tp))
            return normalize_ratio(1.0 - min(age_days / game_day_horizon, 1.0))
        except (KeyError, TypeError, ValueError):
            return 0.0

    # Wall-clock nodes (Event, etc.): score by ISO timestamp fields.
    for field in ("occurred_at", "updated_at", "last_graph_updated_at", "created_at"):
        raw_value = payload.get(field)
        if not isinstance(raw_value, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
        return normalize_ratio(1.0 - min(age_hours / 72.0, 1.0))
    return 0.0


def extract_severity_score(payload: dict[str, Any]) -> float:
    # Direct severity field (Event, Secret)
    raw = payload.get("severity")
    if isinstance(raw, (int, float)):
        return normalize_ratio(float(raw) / 100.0)

    # Goal urgency (0–100)
    urgency = payload.get("urgency")
    if isinstance(urgency, (int, float)):
        return normalize_ratio(float(urgency) / 100.0)

    # Belief confidence (0–100)
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        return normalize_ratio(float(confidence) / 100.0)

    # Memory emotional charge (-100 to 100) — use absolute value
    charge = payload.get("emotional_charge")
    if isinstance(charge, (int, float)):
        return normalize_ratio(abs(float(charge)) / 100.0)

    return 0.0


def _records_for_severity(text: str) -> list[dict[str, Any]]:
    """Return every record in a payload, whether it arrived as an object or an array.

    Args:
        text: The item's serialized payload.
    Returns:
        A list of mapping records; empty when the payload is neither, which includes an
        array of plain strings (`session`) and a payload compression truncated mid-token.
    """
    payload = parse_json_object(text)
    if payload:
        return [payload]
    return [row for row in parse_json_list(text) if isinstance(row, dict)]


def extract_severity_score_for_item(item_key: str, text: str) -> float:
    """Score one item's severity on the field its slot declares, across all its records.

    A slot that declares no `severity_field` -- events, and any key the table does not
    claim -- falls back to the generic chain on the representative record, which is exactly
    the behaviour it had before. A slot that declares one but whose records do not carry it
    falls back the same way, so a producer that stops emitting a field degrades instead of
    silently scoring the whole item zero.

    Magnitude, not sign: `emotional_charge` and `reputation_delta` are signed, and a
    reputation loss is as relevant to the turn as a gain of the same size.

    Args:
        item_key: The key carried by the ContextItem, used to look up the declared field.
        text: The item's serialized payload.
    Returns:
        A relevance ratio in [0, 1].
    """
    field = severity_field_for_key(item_key)
    if field is not None:
        values = [
            abs(float(record[field]))
            for record in _records_for_severity(text)
            if isinstance(record.get(field), (int, float))
            and not isinstance(record.get(field), bool)
        ]
        if values:
            return normalize_ratio(max(values) / 100.0)
    return extract_severity_score(payload_for_scoring(text))


def extract_relation_score(
    *,
    item: ContextItem,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
) -> float:
    if item.tier == "tierB":
        return vector_scores.get(item.key, 0.0)
    # item.priority here is the PRODUCER's literal priority (74-98), not a rank position.
    # rank_context_candidates rewrites priority to max(1, 1000 - index) on its output, and
    # every such value clamps to 1.0 through normalize_ratio -- so ranking an already
    # ranked list would flatten this term to a constant and silently delete the signal.
    # Each tier is ranked exactly once, in _rank_and_serialize_tiers. Keep it that way.
    priority_score = normalize_ratio(item.priority / 100.0)
    # 6.2: blend priority with trust toward the event's actor when available.
    if trust_scores and item.key.startswith("event:"):
        trust = trust_scores.get(item.key)
        if trust is not None:
            return 0.5 * priority_score + 0.5 * trust
    return priority_score


def quest_score(*, item: ContextItem, active_quest: dict[str, Any] | None = None) -> float:
    if "quest" in item.key.lower():
        return 1.0
    # 6.4: boost items whose payload references the active quest's target or giver.
    if active_quest is not None:
        ids_to_match = {active_quest.get("target_id"), active_quest.get("giver_id")} - {None}
        if ids_to_match:
            payload = payload_for_scoring(item.text)
            if any(str(v) in ids_to_match for v in payload.values() if isinstance(v, str)):
                return 1.0
    return 0.0


def infer_proximity_hops(key: str, max_proximity_hops: int) -> int:
    lowered = key.lower()
    if lowered.startswith("character:") or lowered.startswith("relation:"):
        return 0
    if lowered.startswith(NPC_SELF_STATE_KEYS):
        return SELF_STATE_PROXIMITY_HOPS
    if lowered.startswith("location:") or lowered.startswith("nearby_npcs"):
        return 1
    if lowered.startswith("event:"):
        return 1
    if lowered.startswith("session"):
        return 0
    if lowered.startswith("rag:"):
        return max_proximity_hops + 1
    return max_proximity_hops


def normalize_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))
