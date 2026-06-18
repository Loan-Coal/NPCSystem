"""
Module: relation_phase_write_port
Layer: engines
Purpose: Structural Protocol for persisting a RELATES_TO edge's relationship phase, so the
         relationship phase applier depends on one write abstraction and holds no Neo4j
         session (DEC-122 / SEV-24). Paired with the shared RelationReadPort for the read.
Does NOT: open sessions, run Cypher, derive the phase, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/relationship/phase_transition_applier; implemented structurally by
         npc_engine.graph.repositories.relation_phase_write_repository
         .Neo4jRelationPhaseWriteRepository.
"""

from __future__ import annotations

from typing import Protocol


class RelationPhaseWritePort(Protocol):
    """Write-only access to a directed RELATES_TO edge's persisted phase."""

    async def write_relationship_phase(
        self, *, src_id: str, dst_id: str, phase: str, tick: int
    ) -> None:
        """Persist the new relationship_phase + phase_started_at_tick on the edge."""
        ...
