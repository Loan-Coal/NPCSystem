"""
test_reputation_integration.py - Integration tests for reputation graph operations.

Does NOT: validate HTTP route wiring or LLM calls.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.graph.reputation_service import ReputationService
from npc_engine.utils.errors import ReputationNotFoundError


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


async def _create_character(tx, char_id: str) -> None:
    await tx.run(
        "MERGE (c:Character {id: $id}) SET c.name = $id, c.is_active = true",
        id=char_id,
    )


async def _create_faction(tx, faction_id: str) -> None:
    await tx.run(
        "MERGE (f:Faction {id: $id}) SET f.name = $id, f.is_active = true",
        id=faction_id,
    )


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)


@pytest.mark.asyncio
async def test_set_and_read_reputation() -> None:
    """set_reputation → get_reputation returns the correct standing."""
    uri, user, password = _skip_if_no_neo4j()

    char_id = _uid("chr")
    faction_id = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_id)
                await _create_faction(tx, faction_id)
                await tx.commit()

            service = ReputationService(session)
            await service.set_reputation(character_id=char_id, faction_id=faction_id, standing=65)
            result = await service.get_reputation(character_id=char_id, faction_id=faction_id)

        assert result is not None
        assert result["standing"] == 65
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_id, faction_id)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_adjust_reputation_clamps_correctly() -> None:
    """adjust_reputation clamps values that exceed [-100, 100]."""
    uri, user, password = _skip_if_no_neo4j()

    char_id = _uid("chr")
    faction_id = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_id)
                await _create_faction(tx, faction_id)
                await tx.commit()

            service = ReputationService(session)
            await service.set_reputation(character_id=char_id, faction_id=faction_id, standing=90)
            new_standing = await service.adjust_reputation(
                character_id=char_id, faction_id=faction_id, delta=50
            )
            assert new_standing == 100

            new_standing = await service.adjust_reputation(
                character_id=char_id, faction_id=faction_id, delta=-250
            )
            assert new_standing == -100
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_id, faction_id)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_list_reputations_returns_all_edges() -> None:
    """list_reputations returns all HAS_REPUTATION_WITH edges for a character."""
    uri, user, password = _skip_if_no_neo4j()

    char_id = _uid("chr")
    fac_a = _uid("fac")
    fac_b = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_id)
                await _create_faction(tx, fac_a)
                await _create_faction(tx, fac_b)
                await tx.commit()

            service = ReputationService(session)
            await service.set_reputation(character_id=char_id, faction_id=fac_a, standing=30)
            await service.set_reputation(character_id=char_id, faction_id=fac_b, standing=-10)
            reputations = await service.list_reputations(character_id=char_id)

        faction_ids = {r["faction_id"] for r in reputations}
        assert fac_a in faction_ids
        assert fac_b in faction_ids
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_id, fac_a, fac_b)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_set_reputation_raises_when_faction_missing() -> None:
    """set_reputation raises ReputationNotFoundError when faction does not exist."""
    uri, user, password = _skip_if_no_neo4j()

    char_id = _uid("chr")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_id)
                await tx.commit()

            service = ReputationService(session)
            with pytest.raises(ReputationNotFoundError):
                await service.set_reputation(
                    character_id=char_id, faction_id="nonexistent_faction", standing=50
                )
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_id)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_reputation_context_included_above_threshold() -> None:
    """get_reputation_context_for_npc returns items when |standing| >= threshold."""
    uri, user, password = _skip_if_no_neo4j()

    player_id = _uid("player")
    npc_id = _uid("npc")
    faction_id = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, player_id)
                await _create_character(tx, npc_id)
                await _create_faction(tx, faction_id)
                # NPC joins the faction
                await tx.run(
                    """
                    MATCH (c:Character {id: $npc_id})
                    MATCH (f:Faction {id: $faction_id})
                    MERGE (c)-[r:MEMBER_OF]->(f)
                    SET r.role = 'member', r.status = 'active', r.joined_at = datetime()
                    """,
                    npc_id=npc_id,
                    faction_id=faction_id,
                )
                await tx.commit()

            service = ReputationService(session)
            # Standing below threshold → not included
            await service.set_reputation(character_id=player_id, faction_id=faction_id, standing=10)
            items = await service.get_reputation_context_for_npc(
                npc_id=npc_id, player_id=player_id, threshold=20
            )
            assert items == []

            # Standing above threshold → included
            await service.set_reputation(character_id=player_id, faction_id=faction_id, standing=50)
            items = await service.get_reputation_context_for_npc(
                npc_id=npc_id, player_id=player_id, threshold=20
            )
            assert len(items) == 1
            assert items[0]["standing"] == 50
            assert items[0]["label"] == "friendly"
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, player_id, npc_id, faction_id)
                await tx.commit()
        await driver.close()
