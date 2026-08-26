"""
context_scoring.py - Relevance scoring helpers for context tier items.
Layer: retrieval
Purpose: Relevance scoring helpers for context tier items.

Does NOT: fetch graph/vector data or enforce token budgets.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from npc_engine.common.json_utils import parse_json_list, parse_json_object
from .context_merger import ContextItem
from .context_relevance_engine import ContextRelevanceCandidate, rank_context_candidates
from .context_utils import parse_node_identity
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.world.time_utils import TimePoint, total_days


NPC_SELF_STATE_KEYS: tuple[str, ...] = (
    "beliefs",
    "goals",
    "memories",
    "secrets",
    "obligations",
    "owned_items",
    "believed_rumors",
    "traits",
    "group_memberships",
    "active_pledges",
    "player_memories",
    "top_need",
)
"""Context keys carrying state that hangs directly off the NPC's own Character node.

ISSUE-163: these fell through to the ``max_proximity_hops`` default, scoring proximity
0.0 — the score of a node at the graph horizon — so an NPC's own beliefs and memories
ranked below the strangers standing in the room with it (``nearby_npcs``, 1 hop, 0.5).
Under the 281-token tier-A cap that ordering is the difference between reaching the
prompt and being dropped.
"""

SELF_STATE_PROXIMITY_HOPS = 0
"""An NPC's own state is zero hops from the NPC, the same as its character node."""


def rank_tier_items(
    *,
    items: list[ContextItem],
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
    active_quest: dict[str, Any] | None = None,
    game_time: TimePoint | None = None,
    weight_profile: str | None = None,
    explicit_node_ids: frozenset[str] = frozenset(),
) -> list[ContextItem]:
    """Score and rank context items by relevance.

    Args:
        items: Unordered context items to rank.
        llm_config: LLM configuration providing relevance weights and proximity settings.
        vector_scores: Map of item key to normalized vector similarity score.
        trust_scores: Optional map of Tier A event item key to trust score (0–1). (6.2)
        active_quest: Optional active quest dict for quest-relevance scoring. (6.4)
        game_time: Current structured game time for scoring game-time nodes. (8.2)
        weight_profile: Named weight profile override (e.g. "investigation"). (8.3)
        explicit_node_ids: Node IDs pinned by the game engine as relevant this turn.
            Matching nodes score explicit=1.0; all others score 0.0.

    Returns:
        Items reordered by descending relevance score with updated priority fields.
    """

    resolved_weights = llm_config.resolve_weights(weight_profile or llm_config.default_weight_profile)
    candidates = [
        _build_candidate(
            item=item,
            llm_config=llm_config,
            vector_scores=vector_scores,
            trust_scores=trust_scores,
            active_quest=active_quest,
            game_time=game_time,
            explicit_node_ids=explicit_node_ids,
        )
        for item in items
    ]
    return rank_context_candidates(
        candidates=candidates,
        weights=resolved_weights,
        max_proximity_hops=llm_config.max_proximity_hops,
    )


def _build_candidate(
    *,
    item: ContextItem,
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
    active_quest: dict[str, Any] | None = None,
    game_time: TimePoint | None = None,
    explicit_node_ids: frozenset[str] = frozenset(),
) -> ContextRelevanceCandidate:
    node_type, node_id = parse_node_identity(item.key)
    payload = _payload_for_scoring(item.text)
    return ContextRelevanceCandidate(
        node_type=node_type,
        node_id=node_id,
        item=item,
        recency=_extract_recency_score(payload, game_time=game_time, game_day_horizon=llm_config.recency_game_day_horizon),
        severity=_extract_severity_score(payload),
        proximity_hops=_infer_proximity_hops(item.key, llm_config.max_proximity_hops),
        relation=_extract_relation_score(item=item, vector_scores=vector_scores, trust_scores=trust_scores),
        quest=_quest_score(item=item, active_quest=active_quest),
        explicit=1.0 if node_id in explicit_node_ids else 0.0,
    )


# Which record represents an ARRAY payload, and why the first one is defensible.
#
# Every producer orders its rows by its own notion of importance, so the first record is the
# one that producer considers strongest -- and where rerank_by_keyword has reordered beliefs,
# goals and secrets, the first record is instead the one most relevant to the player's message.
# Where the ordering key IS the field _extract_severity_score reads, the first record also
# MAXIMISES the score, which is the strongest case for this choice:
#
#     beliefs          ORDER BY confidence DESC   -> reads confidence         aligned
#     goals            ORDER BY urgency DESC      -> reads urgency            aligned
#     secrets          ORDER BY severity DESC     -> reads severity           aligned
#     believed_rumors  sorted by confidence DESC  -> reads confidence         aligned
#     memories         ORDER BY vividness DESC    -> reads emotional_charge   NOT aligned
#     active_pledges   ORDER BY sworn_at_tick     -> reads severity           NOT aligned
#
# The last two are accepted approximations, not oversights: their representative is the most
# vivid memory and the most recently sworn pledge, whose severity-family value is whatever it
# happens to be. See ISSUE-206. Taking a maximum over records would close the gap but needs a
# per-key table of which field to maximise -- the hand-maintained mapping P5 exists to delete.
def _payload_for_scoring(text: str) -> dict[str, Any]:
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


def _extract_recency_score(
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
            return _normalize_ratio(1.0 - min(age_days / game_day_horizon, 1.0))
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
        return _normalize_ratio(1.0 - min(age_hours / 72.0, 1.0))
    return 0.0


def _extract_severity_score(payload: dict[str, Any]) -> float:
    # Direct severity field (Event, Secret)
    raw = payload.get("severity")
    if isinstance(raw, (int, float)):
        return _normalize_ratio(float(raw) / 100.0)

    # Goal urgency (0–100)
    urgency = payload.get("urgency")
    if isinstance(urgency, (int, float)):
        return _normalize_ratio(float(urgency) / 100.0)

    # Belief confidence (0–100)
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        return _normalize_ratio(float(confidence) / 100.0)

    # Memory emotional charge (-100 to 100) — use absolute value
    charge = payload.get("emotional_charge")
    if isinstance(charge, (int, float)):
        return _normalize_ratio(abs(float(charge)) / 100.0)

    return 0.0


def _extract_relation_score(
    *,
    item: ContextItem,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
) -> float:
    if item.tier == "tierB":
        return vector_scores.get(item.key, 0.0)
    # item.priority here is the PRODUCER's literal priority (74-98), not a rank position.
    # rank_context_candidates rewrites priority to max(1, 1000 - index) on its output, and
    # every such value clamps to 1.0 through _normalize_ratio -- so ranking an already
    # ranked list would flatten this term to a constant and silently delete the signal.
    # Each tier is ranked exactly once, in _rank_and_serialize_tiers. Keep it that way.
    priority_score = _normalize_ratio(item.priority / 100.0)
    # 6.2: blend priority with trust toward the event's actor when available.
    if trust_scores and item.key.startswith("event:"):
        trust = trust_scores.get(item.key)
        if trust is not None:
            return 0.5 * priority_score + 0.5 * trust
    return priority_score


def _quest_score(*, item: ContextItem, active_quest: dict[str, Any] | None = None) -> float:
    if "quest" in item.key.lower():
        return 1.0
    # 6.4: boost items whose payload references the active quest's target or giver.
    if active_quest is not None:
        ids_to_match = {active_quest.get("target_id"), active_quest.get("giver_id")} - {None}
        if ids_to_match:
            payload = _payload_for_scoring(item.text)
            if any(str(v) in ids_to_match for v in payload.values() if isinstance(v, str)):
                return 1.0
    return 0.0


def _infer_proximity_hops(key: str, max_proximity_hops: int) -> int:
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


def _normalize_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))
