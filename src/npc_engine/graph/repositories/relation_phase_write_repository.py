"""
Module: relation_phase_write_repository
Layer: graph
Purpose: Neo4j adapter for the relationship-phase write domain. Opens a session per call
         from the injected GraphDB and delegates to relation_phase_writer.write_relationship_phase,
         so the phase applier depends on the RelationPhaseWritePort abstraction and holds no
         session. Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: derive the phase, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies.build_dialogue_handler).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.relations.relation_phase_writer import write_relationship_phase


class Neo4jRelationPhaseWriteRepository:
    """Session-per-call Neo4j adapter for relationship-phase writes (RelationPhaseWritePort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def write_relationship_phase(
        self, *, src_id: str, dst_id: str, phase: str, tick: int
    ) -> None:
        """Open a session and persist the new phase on the RELATES_TO edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await write_relationship_phase(session, src_id, dst_id, phase, tick)
