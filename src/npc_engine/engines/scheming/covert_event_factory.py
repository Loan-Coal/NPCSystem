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

from enum import Enum

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Covert-event constants (DEC-107 Option A sub-decisions)
# ---------------------------------------------------------------------------


class SchemeStepKind(str, Enum):
    """Registry of valid scheme-step event_type values (OCP extension axis).

    Add new members here instead of scattering raw strings. Each member value
    must be registry-valid (a lowercase event_type the graph accepts).
    """

    ADVANCE = "scheme_advance"


# Dedicated event_type so covert scheme steps do NOT match public disruption /
# witness rules that key on real event types (crime, battle, ...). The `event`
# contract's event_type is a required free string, so this is registry-valid.
COVERT_SCHEME_EVENT_TYPE: str = SchemeStepKind.ADVANCE

# Low severity keeps the step below the witness (>=80) and disruption thresholds;
# combined with is_public=False this makes the step covert by construction.
COVERT_SCHEME_EVENT_SEVERITY: int = 15

# Covert steps are never public.
COVERT_SCHEME_EVENT_IS_PUBLIC: bool = False

# Summary template — graph DATA, not an LLM prompt, so the no-prompt-strings-outside-
# prompts/ rule does not apply (DEC-116, verified 2026-06-14). Trace: covert events are
# linked to a Scheme via SCHEME_STEP only; nothing creates a KNOWS_ABOUT/WITNESSED edge
# to them (is_public=False, severity 15 < witness threshold), and mark_scheme_discovered
# only flips scheme.status. LLM dialogue context pulls events exclusively via KNOWS_ABOUT
# (graph/event_queries.py, retrieval/subgraph_retriever.py), so this summary reaches the
# intrigue-board UI (/npc/{id}/schemes) but never the LLM. If a future change links covert
# events via KNOWS_ABOUT, move this template to prompts/scheming/ (re-open DEC-116).
_COVERT_SUMMARY_TEMPLATE: str = (
    "{npc_id} quietly advances a covert scheme (step {step_order}): {goal}"
)


class CovertEventProps(BaseModel):
    """Typed property bag for a covert scheme-advance Event node (SEV-03 L3-13).

    All fields are required so a missing field raises a Pydantic ValidationError at
    build time rather than a Neo4j constraint error at write time.

    Attributes:
        id: Unique Event node ID (UUID hex).
        summary: Human-readable description of the covert step.
        severity: Numeric severity (kept below witness/disruption thresholds).
        location_id: Graph ID of the Location node where the event occurs.
        occurred_at: ISO 8601 timestamp when the event occurred.
        tick_id: Game tick on which the step was minted.
        event_type: Fixed ``scheme_advance`` type to isolate from public events.
        is_public: Always False — covert events are never public.
        last_graph_updated_at: ISO 8601 timestamp of the last graph write.
    """

    id: str
    summary: str
    severity: int
    location_id: str
    occurred_at: str
    tick_id: int
    event_type: str
    is_public: bool
    last_graph_updated_at: str


def build_covert_event_props(
    *,
    event_id: str,
    npc_id: str,
    goal: str,
    step_order: int,
    location_id: str,
    tick_id: int,
    now_iso: str,
) -> CovertEventProps:
    """Build a registry-valid covert Event property model for one scheme step.

    Carries every required `event` field so it passes ``validate_node_write``
    unchanged after ``.model_dump()``. Caller supplies ``event_id`` (uuid) +
    ``now_iso`` (timestamp) so the function stays pure/deterministic.
    ``step_order`` is the 1-based step; ``location_id`` anchors the covert event
    at the schemer's location.

    Returns:
        CovertEventProps ready for validate_node_write(registry, "event", props.model_dump()).
    """
    summary = _COVERT_SUMMARY_TEMPLATE.format(
        npc_id=npc_id, step_order=step_order, goal=goal
    )
    return CovertEventProps(
        id=event_id,
        summary=summary,
        severity=COVERT_SCHEME_EVENT_SEVERITY,
        location_id=location_id,
        occurred_at=now_iso,
        tick_id=tick_id,
        event_type=COVERT_SCHEME_EVENT_TYPE,
        is_public=COVERT_SCHEME_EVENT_IS_PUBLIC,
        last_graph_updated_at=now_iso,
    )
