"""
Module: relation_phase_writer
Layer: graph
Purpose: Persists relationship phase and phase start tick to the RELATES_TO edge in Neo4j.
Does NOT: derive the phase from scalars, validate schema, or call LLM services.
Dependencies injected: AsyncSession (per call).
Used by: engines/relationship/affinity_engine (slice 2 call-site wiring).
"""

from __future__ import annotations

from neo4j import AsyncSession


_CYPHER_SET_RELATIONSHIP_PHASE = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
SET r.relationship_phase = $relationship_phase,
    r.phase_started_at_tick = $phase_started_at_tick
"""


async def write_relationship_phase(
    session: AsyncSession,
    src_id: str,
    dst_id: str,
    phase: str,
    tick: int,
) -> None:
    """Persist relationship_phase and phase_started_at_tick on the RELATES_TO edge.

    Opens and commits its own transaction; callers must not pass an active transaction.

    Args:
        session: Active Neo4j async session used to begin the transaction.
        src_id: ID of the source character node.
        dst_id: ID of the destination character node.
        phase: The new relationship phase string (RelationshipPhase value) to persist.
        tick: The game tick at which the phase transition occurred.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query execution failure.
    """
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            _CYPHER_SET_RELATIONSHIP_PHASE,
            src_id=src_id,
            dst_id=dst_id,
            relationship_phase=phase,
            phase_started_at_tick=tick,
        )
        await tx.commit()
