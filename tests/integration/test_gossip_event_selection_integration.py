"""
test_gossip_event_selection_integration.py - Integration tests for SEV-09.

Exercises CYPHER_SELECT_EVENT against a real Neo4j to verify:
  1. A canonical Event is selected with is_canonical=true (so distortion is skipped).
  2. An Event whose KNOWS_ABOUT edge is 'corrected' is NOT re-selected for sharing.

Does NOT: validate HTTP route wiring or LLM calls.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.gossip.gossip_queries import CYPHER_SELECT_EVENT
from npc_engine.graph.gossip.rumor_trace_service import correct_rumor_at_npc


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _seed_known_event(tx, char_id: str, event_id: str, *, is_canonical: bool) -> None:
    await tx.run(
        """
        MERGE (c:Character {id: $char_id}) SET c.name = $char_id, c.is_active = true
        MERGE (e:Event {id: $event_id})
        SET e.summary = 'the war begins', e.severity = 80,
            e.occurred_at = 1, e.is_canonical = $is_canonical
        MERGE (c)-[k:KNOWS_ABOUT]->(e)
        SET k.knowledge_state = 'knows', k.learned_at_tick = 1
        """,
        char_id=char_id,
        event_id=event_id,
        is_canonical=is_canonical,
    )


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_canonical", [True, False])
async def test_select_event_reports_canonical_flag(is_canonical: bool) -> None:
    """CYPHER_SELECT_EVENT must surface the real is_canonical value."""
    uri, user, password = _skip_if_no_neo4j()
    char = _uid("chr")
    event = _uid("evt")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _seed_known_event(tx, char, event, is_canonical=is_canonical)
                await tx.commit()

            result = await session.run(CYPHER_SELECT_EVENT, sharer_id=char)
            record = await result.single()
            await result.consume()

        assert record is not None
        assert bool(record["is_canonical"]) is is_canonical
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char, event)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_corrected_event_not_reselected() -> None:
    """A corrected KNOWS_ABOUT edge must be excluded from sharer selection."""
    uri, user, password = _skip_if_no_neo4j()
    char = _uid("chr")
    event = _uid("evt")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _seed_known_event(tx, char, event, is_canonical=False)
                await tx.commit()

            await correct_rumor_at_npc(session, npc_id=char, event_id=event)

            result = await session.run(CYPHER_SELECT_EVENT, sharer_id=char)
            record = await result.single()
            await result.consume()

        assert record is None, "corrected event must not be re-selected for sharing"
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char, event)
                await tx.commit()
        await driver.close()
