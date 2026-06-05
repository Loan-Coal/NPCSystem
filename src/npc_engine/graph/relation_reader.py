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

from neo4j import AsyncSession

from npc_engine.graph.relation_writer import get_relation_values
from npc_engine.utils.errors import RelationEdgeNotFoundError


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

        Args:
            src_id: ID of the source character node.
            dst_id: ID of the destination character node.

        Returns:
            Dict with keys "trust", "fear", and "affection" as integers.

        Raises:
            RelationEdgeNotFoundError: If no RELATES_TO edge exists between src and dst.
        """
        tx = await self._session.begin_transaction()
        async with tx:
            return await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
