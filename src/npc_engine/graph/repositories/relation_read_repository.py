"""
Module: relation_read_repository
Layer: graph
Purpose: Neo4j adapter for the shared relation-read domain. Opens a session per call from
         the injected GraphDB and delegates to RelationReader, so engines depend on the
         RelationReadPort abstraction and hold no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: derive standing/phase, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (engines reading RELATES_TO edges).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.relations.relation_phase_reader import RelationPhaseRow
from npc_engine.graph.relations.relation_reader import RelationReader


class Neo4jRelationReadRepository:
    """Session-per-call Neo4j adapter for relation reads (RelationReadPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        """Open a session and return the trust/fear/affection scalars for the edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await RelationReader(session).get_relation_scalars(
                src_id=src_id, dst_id=dst_id
            )

    async def get_relation_phase_row(
        self, *, src_id: str, dst_id: str
    ) -> RelationPhaseRow | None:
        """Open a session and return the edge's scalars plus persisted phase row."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await RelationReader(session).get_relation_phase_row(
                src_id=src_id, dst_id=dst_id
            )
