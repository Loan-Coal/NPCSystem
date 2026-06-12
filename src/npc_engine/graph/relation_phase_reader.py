"""
Module: relation_phase_reader
Layer: graph
Purpose: Session-scoped read of a RELATES_TO edge's affinity scalars plus the
         persisted relationship_phase, so an engine can decide whether a phase
         transition occurred after a relation delta.
Does NOT: derive the phase, mutate graph state, or call LLM services.
Dependencies injected: neo4j.AsyncSession (per call).
Used by: engines/relationship/phase_transition_applier.
"""

from __future__ import annotations

from neo4j import AsyncSession
from pydantic import BaseModel


_CYPHER_GET_RELATION_PHASE_STATE = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
RETURN coalesce(r.trust, 0) AS trust,
       coalesce(r.fear, 0) AS fear,
       coalesce(r.affection, 0) AS affection,
       r.relationship_phase AS relationship_phase
"""


class RelationPhaseRow(BaseModel):
    """Snapshot of a RELATES_TO edge's affinity scalars and current phase.

    Attributes:
        trust: Current trust scalar (0 when unset).
        fear: Current fear scalar (0 when unset).
        affection: Current affection scalar (0 when unset).
        relationship_phase: Persisted phase string, or None if never transitioned.
    """

    trust: int
    fear: int
    affection: int
    relationship_phase: str | None

    model_config = {"frozen": True}


async def get_relation_phase_state(
    *, session: AsyncSession, src_id: str, dst_id: str
) -> RelationPhaseRow | None:
    """Read the directed RELATES_TO edge's scalars and persisted phase.

    Opens and commits its own read transaction; callers must not pass an active
    transaction.

    Args:
        session: Active Neo4j async session used to begin the transaction.
        src_id: ID of the source character node.
        dst_id: ID of the destination character node.

    Returns:
        RelationPhaseRow when the edge exists, else None (no RELATES_TO edge).

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await tx.run(_CYPHER_GET_RELATION_PHASE_STATE, src_id=src_id, dst_id=dst_id)
        record = await result.single()
        if record is None:
            return None
        return RelationPhaseRow(
            trust=record["trust"],
            fear=record["fear"],
            affection=record["affection"],
            relationship_phase=record["relationship_phase"],
        )
