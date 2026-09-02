"""
test_is_active_reader_agreement_integration.py - Pins the strict `is_active` convention
settled by DEC-252 (ISSUE-258): a Character that lacks the field is invisible to every
reader, not visible to one of them.

Does NOT: exercise HTTP routes, LLMs, or the tick scheduler.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.character.character_reader import get_npc_ids
from npc_engine.graph.graph_reader import get_npc_location_id


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


CYPHER_MERGE_WITHOUT_IS_ACTIVE = """
MERGE (c:Character {id: $id})
SET c.name = $id, c.is_player = false
REMOVE c.is_active
"""

CYPHER_MERGE_WITH_IS_ACTIVE = """
MERGE (c:Character {id: $id})
SET c.name = $id, c.is_player = false, c.is_active = true
"""

CYPHER_PLACE_AT_LOCATION = """
MATCH (c:Character {id: $id})
MERGE (l:Location {id: $location_id})
MERGE (c)-[:LOCATED_AT]->(l)
"""

CYPHER_CLEANUP = """
MATCH (c:Character) WHERE c.id IN $ids DETACH DELETE c
"""

CYPHER_CLEANUP_LOCATION = """
MATCH (l:Location {id: $location_id}) DETACH DELETE l
"""


@pytest.mark.asyncio
async def test_a_character_without_is_active_is_invisible_to_every_reader() -> None:
    """An absent `is_active` means not active, in the roster reader as well as the rest.

    Before DEC-252, `character_reader.get_npc_ids` used
    `coalesce(c.is_active, true) = true` while 36 other predicates used a bare
    `c.is_active = true`. The same node was therefore in the NPC roster and absent from
    every location, memory and skill query -- the divergence that hid ISSUE-233 item 8
    for a whole programme phase, because the failing read logged at DEBUG and said
    nothing. This test fails on the `coalesce` reader and passes on the bare predicate.
    """
    uri, user, password = _skip_if_no_neo4j()
    missing_id = _uid("npc-no-flag")
    present_id = _uid("npc-with-flag")
    location_id = _uid("loc")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            await session.run(CYPHER_MERGE_WITHOUT_IS_ACTIVE, id=missing_id)
            await session.run(CYPHER_MERGE_WITH_IS_ACTIVE, id=present_id)
            await session.run(CYPHER_PLACE_AT_LOCATION, id=missing_id, location_id=location_id)
            await session.run(CYPHER_PLACE_AT_LOCATION, id=present_id, location_id=location_id)

            roster = await get_npc_ids(session)
            missing_location = await get_npc_location_id(session, missing_id)
            present_location = await get_npc_location_id(session, present_id)

        assert missing_id not in roster, (
            "a Character without is_active must not appear in the NPC roster; "
            "the roster reader disagreeing with the location reader is ISSUE-258"
        )
        assert present_id in roster
        assert missing_location is None
        assert present_location == location_id
    finally:
        async with driver.session() as session:
            await session.run(CYPHER_CLEANUP, ids=[missing_id, present_id])
            await session.run(CYPHER_CLEANUP_LOCATION, location_id=location_id)
        await driver.close()
