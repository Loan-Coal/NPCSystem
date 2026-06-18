"""
Module: scheming_engine
Layer: engines
Purpose: Forms capped Scheme nodes (respects MAX_ACTIVE_SCHEMES_PER_NPC) and
         advances one scheme step by delegating to the graph layer via SchemingGraphPort.
Does NOT: call LLMs, query Neo4j directly, perform detection/investigation,
          wire into the tick scheduler, or change any type_registry YAML.
Dependencies injected: Settings + SchemingGraphPort (constructor).
Used by: (slice 2) scheduler tick handler; not yet wired.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from npc_engine.config import Settings
from npc_engine.engines.ports.scheming_port import SchemingGraphPort
from npc_engine.graph.scheme_reader import SchemeRecord

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
    """Input to advance_step — describes the step to persist.

    Attributes:
        scheme_id: ID of the Scheme node to attach the step to.
        event_id: ID of the Event node that represents this step.
        step_order: Ordinal position of this step in the scheme.
        completed: Whether the step has been completed.
    """

    scheme_id: str
    event_id: str
    step_order: int
    completed: bool


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SchemingEngine:
    """Manages scheme formation and step advancement for NPCs.

    Enforces MAX_ACTIVE_SCHEMES_PER_NPC cap before forming a new scheme.
    All persistence is delegated to SchemingGraphPort (no direct Cypher here).
    """

    def __init__(self, settings: Settings, scheming_repo: SchemingGraphPort) -> None:
        """Initialise the scheming engine.

        Args:
            settings: Application settings providing MAX_ACTIVE_SCHEMES_PER_NPC.
            scheming_repo: Graph port for scheme reads and writes.
        """
        self._max_active = settings.MAX_ACTIVE_SCHEMES_PER_NPC
        self._repo = scheming_repo

    async def form_scheme(
        self,
        inputs: SchemeInput,
    ) -> SchemeRecord | None:
        """Form a new scheme for an NPC if the active-scheme cap allows it.

        Counts the NPC's active EXECUTES_SCHEME edges. Returns None (cap reached)
        when the count is already at MAX_ACTIVE_SCHEMES_PER_NPC; otherwise
        writes the Scheme node + EXECUTES_SCHEME edge and returns a SchemeRecord.

        Args:
            inputs: SchemeInput carrying the NPC ID, goal, and current tick.

        Returns:
            SchemeRecord for the newly created scheme, or None if capped.
        """
        active = await self._repo.get_active_schemes(inputs.npc_id)
        if len(active) >= self._max_active:
            return None

        scheme_id = f"{inputs.npc_id}__{uuid.uuid4().hex[:8]}"
        await self._repo.upsert_scheme(
            scheme_id=scheme_id,
            npc_id=inputs.npc_id,
            goal=inputs.goal,
            tick=inputs.tick,
        )
        return SchemeRecord(
            id=scheme_id,
            npc_id=inputs.npc_id,
            goal=inputs.goal,
            status="active",
            created_at_game_time=str(inputs.tick),
        )

    async def advance_step(
        self,
        inputs: SchemeStepInput,
    ) -> None:
        """Record one scheme step by creating or updating a SCHEME_STEP edge.

        Delegates entirely to the graph port. Idempotent: calling with the same
        (scheme_id, event_id) updates the edge.

        Args:
            inputs: SchemeStepInput carrying scheme, event, order, and completion flag.
        """
        await self._repo.add_scheme_step(
            scheme_id=inputs.scheme_id,
            event_id=inputs.event_id,
            step_order=inputs.step_order,
            completed=inputs.completed,
        )

