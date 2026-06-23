"""
Module: relation_read_port
Layer: engines
Purpose: Shared structural Protocol for reading RELATES_TO edge state (trust/fear/
         affection scalars + persisted phase row), so engines that need relation reads
         (reputation, player_model, director, relationship) depend on one abstraction
         instead of constructing a per-tick RelationReader(session) and holding a session.
         Implemented in graph/repositories/relation_read_repository.py.
Does NOT: open sessions, run Cypher, derive standing/phase, or import graph reader/writer
          functions (only the RelationPhaseRow domain model for the return type).
Dependencies injected: none (pure interface).
Used by: future reputation/player_model/director/relationship slices; implemented
         structurally by
         npc_engine.graph.repositories.relation_read_repository.Neo4jRelationReadRepository.
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.graph.relations.relation_phase_reader import RelationPhaseRow


class RelationReadPort(Protocol):
    """Read-only access to a directed RELATES_TO edge's scalars and phase row."""

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        """Return the raw trust/fear/affection scalars for a directed relation edge."""
        ...

    async def get_relation_phase_row(
        self, *, src_id: str, dst_id: str
    ) -> RelationPhaseRow | None:
        """Return the edge's scalars plus persisted phase, or None when no edge exists."""
        ...
