"""
test_faction_gossip_integration.py - Integration tests for faction-aware gossip pair selection.

Does NOT: validate HTTP route wiring or LLM calls.

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.pair_selector import select_pairs
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.gossip_repository import Neo4jGossipRepository


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _skip_if_no_neo4j() -> tuple[str, str, str]:
    uri = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USER", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return uri, user, password


def _make_repo(uri: str, user: str, password: str) -> Neo4jGossipRepository:
    """Build a Neo4jGossipRepository from raw connection parameters."""
    settings = MagicMock()
    settings.NEO4J_URI = uri
    settings.NEO4J_USER = user
    settings.NEO4J_PASSWORD = password
    graph_db = GraphDB(settings)
    return Neo4jGossipRepository(graph_db)


_WEIGHT_CONFIG = GossipWeightConfig()


async def _create_character(tx, char_id: str, loc_id: str, gossipy: int = 50) -> None:
    await tx.run(
        """
        MERGE (c:Character {id: $id})
        SET c.name = $id, c.is_player = false, c.is_active = true, c.gossipy = $gossipy
        MERGE (l:Location {id: $loc_id})
        SET l.name = $loc_id
        MERGE (c)-[:LOCATED_AT]->(l)
        """,
        id=char_id,
        loc_id=loc_id,
        gossipy=gossipy,
    )


async def _create_faction(tx, faction_id: str) -> None:
    await tx.run(
        "MERGE (f:Faction {id: $id}) SET f.name = $id, f.is_active = true",
        id=faction_id,
    )


async def _add_member(tx, char_id: str, faction_id: str) -> None:
    await tx.run(
        """
        MATCH (c:Character {id: $char_id})
        MATCH (f:Faction {id: $faction_id})
        MERGE (c)-[r:MEMBER_OF]->(f)
        SET r.role = 'member', r.status = 'active', r.joined_at = datetime()
        """,
        char_id=char_id,
        faction_id=faction_id,
    )


async def _set_standing(tx, src_id: str, dst_id: str, standing: int) -> None:
    await tx.run(
        """
        MATCH (a:Faction {id: $src_id})
        MATCH (b:Faction {id: $dst_id})
        MERGE (a)-[r:STANDS_WITH]->(b)
        SET r.standing = $standing, r.last_changed_at = datetime()
        """,
        src_id=src_id,
        dst_id=dst_id,
        standing=standing,
    )


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run(
            "MATCH (n {id: $id}) DETACH DELETE n",
            id=node_id,
        )


@pytest.mark.asyncio
async def test_same_faction_pairs_rank_higher_than_strangers() -> None:
    """Same-faction pairs must appear before unfactioned pairs at equal gossipy."""
    uri, user, password = _skip_if_no_neo4j()

    loc = _uid("loc")
    char_a = _uid("chr")
    char_b = _uid("chr")
    char_c = _uid("chr")
    char_d = _uid("chr")
    faction = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_a, loc, gossipy=50)
                await _create_character(tx, char_b, loc, gossipy=50)
                await _create_character(tx, char_c, loc, gossipy=50)
                await _create_character(tx, char_d, loc, gossipy=50)
                await _create_faction(tx, faction)
                await _add_member(tx, char_a, faction)
                await _add_member(tx, char_b, faction)
                await tx.commit()

        repo = _make_repo(uri, user, password)
        pairs = await select_pairs(repo=repo, max_pairs=20, weight_config=_WEIGHT_CONFIG)

        faction_pair_ids = {frozenset([char_a, char_b])}
        unfactioned_pair_ids = {
            frozenset([char_c, char_d]),
            frozenset([char_a, char_c]),
            frozenset([char_b, char_d]),
        }

        returned_ids = [frozenset([s["id"], r["id"]]) for s, r, _, _ in pairs]

        faction_positions = [i for i, ids in enumerate(returned_ids) if ids in faction_pair_ids]
        unfactioned_positions = [i for i, ids in enumerate(returned_ids) if ids in unfactioned_pair_ids]

        assert faction_positions, "same-faction pair not found in results"
        assert unfactioned_positions, "unfactioned pairs not found in results"
        assert min(faction_positions) < max(unfactioned_positions), (
            "same-faction pair should rank higher than unfactioned pairs"
        )
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_a, char_b, char_c, char_d, faction, loc)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_hostile_pairs_rank_lower_than_neutral_pairs() -> None:
    """Hostile-faction pairs must rank below neutral pairs at equal gossipy."""
    uri, user, password = _skip_if_no_neo4j()

    loc = _uid("loc")
    char_a = _uid("chr")
    char_b = _uid("chr")
    char_c = _uid("chr")
    char_d = _uid("chr")
    fac_x = _uid("fac")
    fac_y = _uid("fac")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_a, loc, gossipy=50)
                await _create_character(tx, char_b, loc, gossipy=50)
                await _create_character(tx, char_c, loc, gossipy=50)
                await _create_character(tx, char_d, loc, gossipy=50)
                await _create_faction(tx, fac_x)
                await _create_faction(tx, fac_y)
                await _add_member(tx, char_a, fac_x)
                await _add_member(tx, char_b, fac_y)
                await _set_standing(tx, fac_x, fac_y, -100)
                await _set_standing(tx, fac_y, fac_x, -100)
                await tx.commit()

        repo = _make_repo(uri, user, password)
        pairs = await select_pairs(repo=repo, max_pairs=20, weight_config=_WEIGHT_CONFIG)

        hostile_pair_ids = {frozenset([char_a, char_b])}
        neutral_pair_ids = {frozenset([char_c, char_d])}

        returned_ids = [frozenset([s["id"], r["id"]]) for s, r, _, _ in pairs]

        hostile_positions = [i for i, ids in enumerate(returned_ids) if ids in hostile_pair_ids]
        neutral_positions = [i for i, ids in enumerate(returned_ids) if ids in neutral_pair_ids]

        assert hostile_positions, "hostile pair not found in results"
        assert neutral_positions, "neutral pair not found in results"
        assert min(neutral_positions) < max(hostile_positions), (
            "neutral pairs should rank higher than hostile pairs"
        )
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_a, char_b, char_c, char_d, fac_x, fac_y, loc)
                await tx.commit()
        await driver.close()


@pytest.mark.asyncio
async def test_faction_context_included_in_pair_tuples() -> None:
    """select_pairs must return 4-tuples with faction_ctx containing expected keys."""
    uri, user, password = _skip_if_no_neo4j()

    loc = _uid("loc")
    char_a = _uid("chr")
    char_b = _uid("chr")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_character(tx, char_a, loc)
                await _create_character(tx, char_b, loc)
                await tx.commit()

        repo = _make_repo(uri, user, password)
        pairs = await select_pairs(repo=repo, max_pairs=10, weight_config=_WEIGHT_CONFIG)

        assert len(pairs) >= 2
        for tup in pairs:
            assert len(tup) == 4
            _sharer, _receiver, _loc, faction_ctx = tup
            assert "a_faction_ids" in faction_ctx
            assert "b_faction_ids" in faction_ctx
            assert "best_standing" in faction_ctx
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, char_a, char_b, loc)
                await tx.commit()
        await driver.close()
