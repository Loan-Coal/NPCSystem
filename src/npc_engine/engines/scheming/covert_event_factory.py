"""
Module: covert_event_factory
Layer: engines
Purpose: Pure builder for the registry-valid covert Event property dict that a
         scheme advance (DEC-107 Option A) links as its next SCHEME_STEP.
Does NOT: call LLMs, touch Neo4j, validate against the registry, or create UUIDs
          (the caller supplies event_id so the function stays pure/deterministic).
Dependencies injected: none (stateless free functions).
Used by: engines/scheming/scheme_advance_tick.py
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Covert-event constants (DEC-107 Option A sub-decisions)
# ---------------------------------------------------------------------------

# Dedicated event_type so covert scheme steps do NOT match public disruption /
# witness rules that key on real event types (crime, battle, ...). The `event`
# contract's event_type is a required free string, so this is registry-valid.
COVERT_SCHEME_EVENT_TYPE: str = "scheme_advance"

# Low severity keeps the step below the witness (>=80) and disruption thresholds;
# combined with is_public=False this makes the step covert by construction.
COVERT_SCHEME_EVENT_SEVERITY: int = 15

# Covert steps are never public.
COVERT_SCHEME_EVENT_IS_PUBLIC: bool = False

# Summary template — content data, not an LLM prompt (no prompts/ rule applies).
_COVERT_SUMMARY_TEMPLATE: str = (
    "{npc_id} quietly advances a covert scheme (step {step_order}): {goal}"
)


def build_covert_event_props(
    *,
    event_id: str,
    npc_id: str,
    goal: str,
    step_order: int,
    location_id: str,
    tick_id: int,
    now_iso: str,
) -> dict[str, Any]:
    """Build a registry-valid covert Event property dict for one scheme step.

    Carries every required `event` field so it passes ``validate_node_write``
    unchanged. Caller supplies ``event_id`` (uuid) + ``now_iso`` (timestamp) so
    the function stays pure/deterministic. ``step_order`` is the 1-based step;
    ``location_id`` anchors the covert event at the schemer's location.

    Returns:
        Property dict ready for validate_node_write(registry, "event", props).
    """
    summary = _COVERT_SUMMARY_TEMPLATE.format(
        npc_id=npc_id, step_order=step_order, goal=goal
    )
    return {
        "id": event_id,
        "summary": summary,
        "severity": COVERT_SCHEME_EVENT_SEVERITY,
        "location_id": location_id,
        "occurred_at": now_iso,
        "tick_id": tick_id,
        "event_type": COVERT_SCHEME_EVENT_TYPE,
        "is_public": COVERT_SCHEME_EVENT_IS_PUBLIC,
        "last_graph_updated_at": now_iso,
    }
