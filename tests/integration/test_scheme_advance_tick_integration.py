"""
test_scheme_advance_tick_integration.py - Integration test for F1.6 / DEC-107 Option A:
the SchemeAdvanceTick adapter mints a registry-valid covert Event and links it as the
next SCHEME_STEP for an active scheme.

Does NOT: validate HTTP routes, LLMs, or detection (status flip is F1.6 slice 2).

Dependencies injected: Neo4j test environment via env vars; the real TypeRegistry.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.api.dependencies_infra import get_type_registry
from npc_engine.config import get_settings
from npc_engine.engines.scheming.scheme_advance_tick import SchemeAdvanceTick
from npc_engine.graph.db import GraphDB
from npc_engine.graph.repositories.scheming_repository import Neo4jSchemingRepository
from npc_engine.graph.scheme_reader import get_all_active_schemes_with_steps
from npc_engine.graph.scheme_writer import upsert_scheme


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _setup(tx, npc_id: str, loc_id: str) -> None:
    await tx.run(
        "MERGE (c:Character {id: $npc_id}) "
        "MERGE (l:Location {id: $loc_id}) "
        "MERGE (c)-[:LOCATED_AT]->(l)",
        npc_id=npc_id, loc_id=loc_id,
    )


async def _read_step_event(tx, scheme_id: str):
    result = await tx.run(
        "MATCH (s:Scheme {id: $sid})-[st:SCHEME_STEP]->(e:Event) "
        "RETURN e.event_type AS event_type, e.is_public AS is_public, "
        "st.step_order AS step_order",
        sid=scheme_id,
    )
    return await result.single()


async def _cleanup(tx, npc_id: str, loc_id: str, scheme_id: str) -> None:
    await tx.run(
        "MATCH (s:Scheme {id: $sid})-[:SCHEME_STEP]->(e:Event) DETACH DELETE e",
        sid=scheme_id,
    )
    for node_id in (npc_id, loc_id, scheme_id):
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
async def test_advance_creates_covert_event_and_step() -> None:
    """run_tick mints a covert Event (is_public=false) + SCHEME_STEP for an active scheme."""
    uri, user, password = _skip_if_no_neo4j()

    npc_id = _uid("npc")
    loc_id = _uid("loc")
    scheme_id = ""

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _setup(tx, npc_id, loc_id)
                await tx.commit()

            await upsert_scheme(
                session=session, scheme_id=_uid("scheme"),
                npc_id=npc_id, goal="rob the vault", tick=1,
            )
            # Recover the scheme_id we just created for this npc.
            schemes = await get_all_active_schemes_with_steps(session)
            mine = [s for s in schemes if s.npc_id == npc_id]
            assert len(mine) == 1
            scheme_id = mine[0].scheme_id
            assert mine[0].step_count == 0

            graph_db = GraphDB(settings=get_settings())
            repo = Neo4jSchemingRepository(graph_db=graph_db)
            adapter = SchemeAdvanceTick(
                settings=get_settings(),
                registry=get_type_registry(),
                scheming_repo=repo,
            )
            # Interval default is 5; tick 10 is on-cadence.
            result = await adapter.run_tick(tick_id=10)
            assert result["advanced"] == 1

            async with await session.begin_transaction() as tx:
                row = await _read_step_event(tx, scheme_id)

        assert row is not None
        assert row["event_type"] == "scheme_advance"
        assert row["is_public"] is False
        assert row["step_order"] == 1
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, npc_id, loc_id, scheme_id or "none")
                await tx.commit()
        await driver.close()
