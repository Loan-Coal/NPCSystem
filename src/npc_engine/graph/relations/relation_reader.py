"""
Module: relation_reader
Layer: graph
Purpose: Session-scoped read service for RELATES_TO edge scalars (trust, fear, affection).
         Wraps the existing get_relation_values query function behind a session interface
         so callers never open their own transactions.
Does NOT: mutate graph state, call LLM services, or derive higher-level standing values.
Dependencies injected: neo4j.AsyncSession (caller-managed via FastAPI DI).
Used by: npc_engine.api.routes.relationship
"""

from __future__ import annotations

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.graph.relations.relation_phase_reader import RelationPhaseRow, get_relation_phase_state
from npc_engine.graph.relations.relation_writer import get_relation_values
from npc_engine.graph.infra.transaction_coordinator import run_in_tx


class RelationReader:
    """Session-scoped reader for RELATES_TO edge scalar values.

    Opens a read transaction per call; callers must not manage transactions directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the reader with an injected Neo4j session.

        Args:
            session: Active Neo4j async session for the current request.
        """
        self._session = session

    async def get_relation_scalars(self, *, src_id: str, dst_id: str) -> dict[str, int]:
        """Return the raw trust, fear, and affection scalars for a directed relation edge.

        The read runs inside a transaction owned by the graph transaction
        coordinator (``run_in_tx``).

        Args:
            src_id: ID of the source character node.
            dst_id: ID of the destination character node.

        Returns:
            Dict with keys "trust", "fear", and "affection" as integers.

        Raises:
            RelationEdgeNotFoundError: If no RELATES_TO edge exists between src and dst.
        """
        async def _work(tx: AsyncTransaction) -> dict[str, int]:
            return await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)

        return await run_in_tx(self._session, _work)

    async def get_relation_phase_row(self, *, src_id: str, dst_id: str) -> RelationPhaseRow | None:
        """Return the edge's scalars plus persisted phase and phase-start tick.

        Args:
            src_id: ID of the source character node.
            dst_id: ID of the destination character node.

        Returns:
            RelationPhaseRow when the RELATES_TO edge exists, else None.
        """
        return await get_relation_phase_state(session=self._session, src_id=src_id, dst_id=dst_id)
