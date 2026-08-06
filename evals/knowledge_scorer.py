"""
Module: knowledge_scorer
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Pure unpropagated-event-reference scorer. Detects mentions of graph event
         IDs in generated NPC text and reports the fraction that the NPC should not
         know about (i.e. absent from its KNOWS_ABOUT-derived known set).
Dependencies: pydantic v2, re
Used by: evals.deterministic_pass

Knowledge sources deliberately excluded from npc_known_event_ids:
- BELIEF nodes (e.g. ah_demo_sorn_walls_belief) — the NPC may hold a belief that
  implies an event without having a direct KNOWS_ABOUT edge.
- GOAL nodes (e.g. ah_demo_sorn_guild_goal) — goals can reference event contexts.
- MEMORY nodes — episodic memories may encode event knowledge implicitly.
- WITNESSED edges — first-hand observation is a valid knowledge source distinct
  from KNOWS_ABOUT propagation.

False-positive risk: If the caller of this scorer only supplies KNOWS_ABOUT-derived
IDs as npc_known_event_ids, mentions grounded in beliefs, goals, memories, or
witnessed edges will be counted as violations even though the NPC's reference is
legitimate. Callers are responsible for including all relevant knowledge sources
in npc_known_event_ids to avoid inflated violation counts.

Detection uses whole-word regex matching (\\b boundaries, case-insensitive) on the
raw event node ID strings. Pronouns and paraphrases are undetectable — documented
limits, not backlog.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RATE_DECIMALS: int = 3

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class KnowledgeScore(BaseModel):
    """Result of the unpropagated-event-reference scorer.

    Attributes:
        references: Total event ID matches found in the text.
        violations: Matches for event IDs absent from npc_known_event_ids.
        rate: violations / references, rounded to 3 decimal places; 0.0 when
              references == 0 (no division-by-zero).
    """

    model_config = ConfigDict(frozen=True)

    references: int
    violations: int
    rate: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compile_event_patterns(
    event_vocabulary: frozenset[str],
) -> list[tuple[re.Pattern[str], str]]:
    """Compile event ID strings into whole-word regex patterns.

    Longer IDs are compiled first so that any ID that is a substring of another
    is shadowed by the longer match (prevents double-counting in pathological
    vocabulary sets).

    Args:
        event_vocabulary: All known event node ID strings.
    Returns:
        List of (compiled pattern, event_id) pairs, sorted by descending ID length.
    """
    sorted_ids = sorted(event_vocabulary, key=lambda eid: -len(eid))
    return [
        (re.compile(r"\b" + re.escape(eid) + r"\b", re.IGNORECASE), eid)
        for eid in sorted_ids
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def unpropagated_references(
    text: str,
    event_vocabulary: frozenset[str],
    npc_known_event_ids: frozenset[str],
) -> KnowledgeScore:
    """Return the fraction of detected event references the NPC should not know.

    Uses whole-word matching on event node ID strings (not NER). Only events
    present in event_vocabulary are searched for. Pronouns and paraphrased
    references are invisible to this scorer.

    Algorithm:
    1. Compile event IDs into whole-word regex patterns (longest first).
    2. Scan text with each pattern; count non-overlapping matches.
    3. For each match, check if the event ID is in npc_known_event_ids.
    4. Accumulate reference and violation counts.
    5. Return KnowledgeScore with totals and rounded rate.

    Args:
        text: NPC generated dialogue or response text.
        event_vocabulary: All event node IDs known to exist in the graph. Only
            IDs in this set are searched for in the text.
        npc_known_event_ids: Event IDs the NPC is permitted to reference.
            Matches for IDs absent from this set count as violations.
    Returns:
        KnowledgeScore with reference count, violation count, and rate.
    """
    patterns = _compile_event_patterns(event_vocabulary)
    remaining = text
    references: int = 0
    violations: int = 0

    for pattern, event_id in patterns:
        matches = pattern.findall(remaining)
        count = len(matches)
        if count:
            references += count
            if event_id not in npc_known_event_ids:
                violations += count
            remaining = pattern.sub(" ", remaining)

    rate = round(violations / references, _RATE_DECIMALS) if references > 0 else 0.0
    return KnowledgeScore(references=references, violations=violations, rate=rate)
