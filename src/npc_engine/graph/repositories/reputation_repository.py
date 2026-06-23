"""
Module: reputation_repository
Layer: graph
Purpose: Neo4j adapter for the reputation-write domain. Opens a session per call from the
         injected GraphDB and delegates to reputation_nudge.apply_trust_nudge, so the
         reputation engine depends on the ReputationGraphPort abstraction and holds no
         session. Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: derive standing, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_engines.get_reputation_engine).
"""

from __future__ import annotations

from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.reputation.reputation_nudge import apply_trust_nudge


class Neo4jReputationRepository:
    """Session-per-call Neo4j adapter for the reputation nudge (ReputationGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def apply_trust_nudge(
        self,
        *,
        src_id: str,
        dst_id: str,
        delta_trust: int,
        delta_affection: int,
    ) -> None:
        """Open a session and apply bounded trust/affection deltas to an existing edge."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await apply_trust_nudge(
                session,
                src_id=src_id,
                dst_id=dst_id,
                delta_trust=delta_trust,
                delta_affection=delta_affection,
            )
