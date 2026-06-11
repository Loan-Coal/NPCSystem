"""
Module: trigger_router
Layer: engines
Purpose: Pure composition layer that selects the highest-priority proactive
         trigger from a list of candidates emitted by the ProactiveDialogueEngine
         and (future) IntentFormationEngine.  Returns one TriggerCandidate or None.
Does NOT: call the LLM, read the graph, emit WebSocket messages, or mutate any
          engine state.  Wiring this result back into the scheduler is slice 2.
Dependencies injected: None (pure function; no stateful collaborators).
Used by: (slice 2) scheduler or tick adapter that collects engine outputs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Priority value floor — candidates below this threshold are still eligible;
# the floor exists so callers can use it as a sentinel "no signal" value.
MIN_VALID_PRIORITY: int = 0

# Tie-break sentinel used when two candidates share identical source and payload.
# The original list order is the final fallback (first-seen wins after sorting).
_STABLE_SORT_SENTINEL: str = ""

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

TriggerSource = Literal["memory", "need", "event"]
"""The originating signal type for a proactive trigger candidate.

- ``"memory"``  — a high-vividness unshared memory from ProactiveDialogueEngine.
- ``"need"``    — an unmet NPC need from IntentFormationEngine (slice 2).
- ``"event"``   — an in-world event that the NPC must react to (slice 2).
"""


class TriggerCandidate(BaseModel):
    """A single proactive-trigger candidate ready for routing.

    Produced by any engine that detects a reason for NPC initiative.
    The router receives a list of these and returns the single winner.

    Attributes:
        source: Which signal type produced this candidate.
        priority: Integer priority score — higher wins.  Callers must use
                  named constants (e.g. ``HIGH_VIVIDNESS_THRESHOLD``) rather
                  than raw literals.
        payload: Opaque string payload forwarded to the consumer (e.g. a
                 memory ID, need label, or event reference).  Must be
                 non-empty for meaningful signals.
    """

    source: TriggerSource = Field(
        ...,
        description="Signal origin: 'memory' | 'need' | 'event'.",
    )
    priority: int = Field(
        ...,
        ge=MIN_VALID_PRIORITY,
        description="Selection priority — higher integer wins.",
    )
    payload: Any = Field(
        ...,
        description="Opaque payload forwarded to the scheduler (memory ID, need label, etc.).",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def select_trigger(
    candidates: list[TriggerCandidate],
) -> TriggerCandidate | None:
    """Select the highest-priority trigger from a list of candidates.

    Tie-breaking is fully deterministic:
    1. Highest ``priority`` value wins.
    2. On equal priority: alphabetically lower ``source`` string wins.
    3. On equal source: alphabetically lower ``str(payload)`` wins.
    4. On equal payload: first occurrence in the original list wins (stable sort).

    Args:
        candidates: Zero or more trigger candidates from engine tick outputs.

    Returns:
        The winning ``TriggerCandidate``, or ``None`` if ``candidates`` is empty.
    """
    if not candidates:
        return None

    # Build an annotated list preserving original index for stable tie-breaking.
    indexed = [(idx, c) for idx, c in enumerate(candidates)]

    def _sort_key(item: tuple[int, TriggerCandidate]) -> tuple[int, str, str, int]:
        idx, c = item
        # Negate priority so highest priority sorts first (ascending sort).
        return (-c.priority, c.source, str(c.payload), idx)

    ranked = sorted(indexed, key=_sort_key)
    _, winner = ranked[0]
    return winner
