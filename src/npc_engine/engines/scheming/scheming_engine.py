"""
Module: scheming_engine
Layer: engines
Purpose: Pydantic input/output models shared by SchemeAdvanceTick and the graph layer.
         The orchestrator class was removed in T4.1 (it was never wired to production).
         SchemeAdvanceTick in scheme_advance_tick.py is the live tick handler.
Does NOT: call LLMs, query Neo4j directly, or wire into the tick scheduler.
Dependencies injected: none (models only).
Used by: engines.scheming.scheme_advance_tick, api routes (slice 2).
"""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Pydantic input/output models
# ---------------------------------------------------------------------------


class SchemeInput(BaseModel):
    """Input to form_scheme — describes the scheme to create.

    Attributes:
        npc_id: NPC that will execute the scheme (EXECUTES_SCHEME source).
        goal: Free-text description of the covert goal.
        tick: Current game tick (stored as started_at_tick on the edge).
    """

    npc_id: str
    goal: str
    tick: int


class SchemeStepInput(BaseModel):
    """Input to advance_step — describes the step to persist atomically (ISSUE-108/DEC-134).

    npc_id, goal, and location_id are required so advance_step can build the
    registry-valid covert Event and write it + SCHEME_STEP in one transaction via
    emit_scheme_step_atomic. The event_id is generated internally by advance_step.

    Attributes:
        scheme_id: ID of the Scheme node to attach the step to.
        npc_id: ID of the NPC executing the scheme (for event summary + actor).
        goal: Scheme goal text (for event summary).
        location_id: Location where the covert event occurs.
        step_order: Ordinal position of this step in the scheme.
        completed: Whether the step has been completed.
        tick: Authoritative game tick the step occurs at. Required — the covert Event
            previously hardcoded tick_id=0 while the sibling SchemeAdvanceTick passed a
            real tick into the same builder, so one node type carried two tick
            semantics (ISSUE-165). Mirrors SchemeInput.tick.
    """

    scheme_id: str
    npc_id: str
    goal: str
    location_id: str
    step_order: int
    completed: bool
    tick: int



