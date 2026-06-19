"""
Module: scheming_engine
Layer: engines
Purpose: Forms capped Scheme nodes (respects MAX_ACTIVE_SCHEMES_PER_NPC) and
         advances one scheme step atomically via SchemingGraphPort.emit_scheme_step_atomic
         (ISSUE-108/DEC-134). When TypeRegistry is injected, advance_step builds a
         registry-valid covert Event and writes it + SCHEME_STEP in one transaction.
Does NOT: call LLMs, query Neo4j directly, perform detection/investigation,
          wire into the tick scheduler, or change any type_registry YAML.
Dependencies injected: Settings + SchemingGraphPort + TypeRegistry (optional, constructor).
Used by: (slice 2) scheduler tick handler; not yet wired.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel

from npc_engine.config import Settings
from npc_engine.engines.ports.scheming_port import SchemingGraphPort
from npc_engine.engines.scheming.covert_event_factory import build_covert_event_props
from npc_engine.graph.scheme_reader import SchemeRecord
from npc_engine.type_registry.node_validator import validate_node_write

if TYPE_CHECKING:
    from npc_engine.type_registry.contracts import TypeRegistry

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
    """

    scheme_id: str
    npc_id: str
    goal: str
    location_id: str
    step_order: int
    completed: bool


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


_EVENT_NODE_TYPE: str = "event"


class SchemingEngine:
    """Manages scheme formation and step advancement for NPCs.

    Enforces MAX_ACTIVE_SCHEMES_PER_NPC cap before forming a new scheme.
    When TypeRegistry is injected, advance_step builds a covert Event and
    writes it + SCHEME_STEP atomically (ISSUE-108/DEC-134).
    All persistence is delegated to SchemingGraphPort (no direct Cypher here).
    """

    def __init__(
        self,
        settings: Settings,
        scheming_repo: SchemingGraphPort,
        registry: TypeRegistry | None = None,
    ) -> None:
        """Initialise the scheming engine.

        Args:
            settings: Application settings providing MAX_ACTIVE_SCHEMES_PER_NPC.
            scheming_repo: Graph port for scheme reads and writes.
            registry: TypeRegistry for building registry-valid covert Event nodes
                when advance_step uses the atomic emit path. When None, advance_step
                falls back to add_scheme_step (non-atomic, legacy behaviour).
        """
        self._max_active = settings.MAX_ACTIVE_SCHEMES_PER_NPC
        self._repo = scheming_repo
        self._registry: TypeRegistry | None = registry

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
        """Record one scheme step atomically (Event + SCHEME_STEP in one transaction).

        When a TypeRegistry is injected, builds a registry-valid covert Event via
        build_covert_event_props and calls emit_scheme_step_atomic so the Event node
        and SCHEME_STEP edge are written atomically (ISSUE-108/DEC-134).

        Args:
            inputs: SchemeStepInput with npc_id, goal, location_id for event construction.

        Raises:
            RuntimeError: When registry is not injected (caller must inject TypeRegistry).
        """
        if self._registry is None:
            raise RuntimeError(
                "SchemingEngine.advance_step requires a TypeRegistry (DEC-134). "
                "Inject registry= via the constructor."
            )
        event_id = uuid.uuid4().hex
        now_iso = datetime.now(timezone.utc).isoformat()
        props = build_covert_event_props(
            event_id=event_id,
            npc_id=inputs.npc_id,
            goal=inputs.goal,
            step_order=inputs.step_order,
            location_id=inputs.location_id,
            tick_id=0,
            now_iso=now_iso,
        )
        validated = validate_node_write(self._registry, _EVENT_NODE_TYPE, props.model_dump())
        event = self._registry.node_models[_EVENT_NODE_TYPE](**validated)
        await self._repo.emit_scheme_step_atomic(
            event=event,
            scheme_id=inputs.scheme_id,
            event_id=event_id,
            step_order=inputs.step_order,
            completed=inputs.completed,
        )

