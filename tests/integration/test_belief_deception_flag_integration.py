"""
test_belief_deception_flag_integration.py - Integration test for F2.5: the beliefs read
surfaces the BELIEVES-edge is_deception flag (buyer-facing "tell") against a live Neo4j.

Does NOT: validate HTTP routes or LLM calls.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.belief_queries import get_beliefs_for_character


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _create_belief(tx, char_id: str, belief_id: str, *, confidence: int, deception: bool) -> None:
    await tx.run(
        "MERGE (c:Character {id: $char_id}) "
        "CREATE (b:Belief {id: $belief_id, content: $belief_id, confidence: $confidence}) "
        "CREATE (c)-[:BELIEVES {is_deception: $deception}]->(b)",
        char_id=char_id, belief_id=belief_id, confidence=confidence, deception=deception,
    )


async def _cleanup(tx, char_id: str) -> None:
    await tx.run(
        "MATCH (c:Character {id: $char_id})-[:BELIEVES]->(b:Belief) DETACH DELETE c, b",
        char_id=char_id,
    )


@pytest.mark.asyncio
async def test_read_surfaces_is_deception_flag() -> None:
    """get_beliefs_for_character returns the per-edge is_deception flag (True/False)."""
    uri, user, password = _skip_if_no_neo4j()

    char_id = _uid("chr")
    deceptive_id = _uid("lie")
    honest_id = _uid("truth")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_belief(tx, char_id, deceptive_id, confidence=90, deception=True)
                await _create_belief(tx, char_id, honest_id, confidence=80, deception=False)
                await tx.commit()

            beliefs = await get_beliefs_for_character(session, character_id=char_id, k=10)

        by_id = {b["id"]: b for b in beliefs}
        assert by_id[deceptive_id]["is_deception"] is True
        assert by_id[honest_id]["is_deception"] is False
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_id)
                await tx.commit()
        await driver.close()
