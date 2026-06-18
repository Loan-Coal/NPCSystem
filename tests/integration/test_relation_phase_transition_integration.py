"""
test_relation_phase_transition_integration.py - Integration test for F1.1 phase
persistence: a relationship phase transition is written to the RELATES_TO edge
after a dialogue turn's relation delta lands.

Does NOT: validate HTTP route wiring or LLM calls (exercises the graph call-site
directly with a live Neo4j edge).

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.engines.relationship.affinity_engine import RelationshipPhase
from npc_engine.engines.relationship.phase_transition_applier import apply_phase_transition
from npc_engine.graph.db import GraphDB
from npc_engine.graph.repositories.relation_phase_write_repository import (
    Neo4jRelationPhaseWriteRepository,
)
from npc_engine.graph.repositories.relation_read_repository import (
    Neo4jRelationReadRepository,
)


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _create_edge(tx, src_id: str, dst_id: str, *, trust: int, fear: int, affection: int) -> None:
    await tx.run(
        "MERGE (a:Character {id: $src_id}) "
        "MERGE (b:Character {id: $dst_id}) "
        "MERGE (a)-[r:RELATES_TO]->(b) "
        "SET r.trust = $trust, r.fear = $fear, r.affection = $affection, "
        "    r.relationship_phase = 'STRANGER'",
        src_id=src_id, dst_id=dst_id, trust=trust, fear=fear, affection=affection,
    )


async def _read_phase(tx, src_id: str, dst_id: str) -> str | None:
    result = await tx.run(
        "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
        "RETURN r.relationship_phase AS phase",
        src_id=src_id, dst_id=dst_id,
    )
    record = await result.single()
    return None if record is None else record["phase"]


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
async def test_phase_transition_persisted_after_delta() -> None:
    """High affinity scalars on the edge persist a CLOSE phase via apply_phase_transition."""
    uri, user, password = _skip_if_no_neo4j()

    npc_id = _uid("npc")
    player_id = _uid("plr")

    graph_db = GraphDB(SimpleNamespace(NEO4J_URI=uri, NEO4J_USER=user, NEO4J_PASSWORD=password))  # type: ignore[arg-type]
    read_repo = Neo4jRelationReadRepository(graph_db)
    write_repo = Neo4jRelationPhaseWriteRepository(graph_db)

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                # composite = trust + affection - fear = 60 + 40 - 5 = 95 -> CLOSE band.
                await _create_edge(tx, npc_id, player_id, trust=60, fear=5, affection=40)
                await tx.commit()

            transition = await apply_phase_transition(
                read_repo, write_repo, src_id=npc_id, dst_id=player_id, tick=120,
            )

            async with await session.begin_transaction() as tx:
                persisted = await _read_phase(tx, npc_id, player_id)

        assert transition is not None
        assert transition.new_phase is RelationshipPhase.CLOSE
        assert persisted == RelationshipPhase.CLOSE.value
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, npc_id, player_id)
                await tx.commit()
        await driver.close()
        await graph_db.close()
