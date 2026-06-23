"""
test_scheme_detection_tick_integration.py - Integration test for F1.6 detection-half:
SchemeDetectionTick flips a witnessed, sufficiently-advanced active scheme to
status 'discovered'.

Does NOT: validate routes, LLMs, or advance (slice 1).

Dependencies injected: Neo4j test environment via env vars.
Uses Neo4jSchemingRepository (DEC-122 / SEV-24 Wave 5 — no session passed to tick).
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.config import get_settings
from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick
from npc_engine.graph.db import GraphDB
from npc_engine.graph.repositories.scheming_repository import Neo4jSchemingRepository
from npc_engine.graph.intrigue.scheme_writer import upsert_scheme


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _setup(tx, schemer: str, witness: str, loc_id: str, scheme_id: str) -> None:
    # Schemer + a co-located witness at the same location.
    await tx.run(
        "MERGE (c:Character {id: $schemer}) "
        "MERGE (w:Character {id: $witness}) "
        "MERGE (l:Location {id: $loc_id}) "
        "MERGE (c)-[:LOCATED_AT]->(l) "
        "MERGE (w)-[:LOCATED_AT]->(l)",
        schemer=schemer, witness=witness, loc_id=loc_id,
    )
    # Two covert step events linked to the scheme (>= SCHEME_DISCOVERY_MIN_STEPS=2).
    for i in range(2):
        await tx.run(
            "MATCH (s:Scheme {id: $sid}) "
            "MERGE (e:Event {id: $eid}) SET e.event_type = 'scheme_advance' "
            "MERGE (s)-[st:SCHEME_STEP]->(e) SET st.step_order = $order",
            sid=scheme_id, eid=f"{scheme_id}-ev{i}", order=i + 1,
        )


async def _read_status(tx, scheme_id: str) -> str | None:
    result = await tx.run("MATCH (s:Scheme {id: $sid}) RETURN s.status AS status", sid=scheme_id)
    record = await result.single()
    return record["status"] if record else None


async def _cleanup(tx, schemer: str, witness: str, loc_id: str, scheme_id: str) -> None:
    await tx.run(
        "MATCH (s:Scheme {id: $sid})-[:SCHEME_STEP]->(e:Event) DETACH DELETE e",
        sid=scheme_id,
    )
    for node_id in (schemer, witness, loc_id, scheme_id):
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
async def test_witnessed_scheme_is_discovered() -> None:
    """A co-located, 2-step active scheme flips to 'discovered' on a detection tick."""
    uri, user, password = _skip_if_no_neo4j()

    schemer = _uid("npc")
    witness = _uid("wit")
    loc_id = _uid("loc")
    scheme_id = _uid("scheme")

    settings = get_settings()
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            await upsert_scheme(
                session=session, scheme_id=scheme_id,
                npc_id=schemer, goal="rob the vault", tick=1,
            )
            async with await session.begin_transaction() as tx:
                await _setup(tx, schemer, witness, loc_id, scheme_id)
                await tx.commit()

        graph_db = GraphDB(settings)
        adapter = SchemeDetectionTick(
            settings=settings,
            scheming_repo=Neo4jSchemingRepository(graph_db=graph_db),
        )
        # Detection interval default is 7; tick 14 is on-cadence.
        result = await adapter.run_tick(tick_id=14)
        assert result["discovered"] == 1

        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                status = await _read_status(tx, scheme_id)

        assert status == "discovered"
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, schemer, witness, loc_id, scheme_id)
                await tx.commit()
        await driver.close()
