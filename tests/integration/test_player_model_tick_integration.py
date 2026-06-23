"""
test_player_model_tick_integration.py - Integration test for F1.4: the PlayerModelTick
adapter persists a PlayerModel node from live RELATES_TO scalars on a tick.

Does NOT: validate HTTP route wiring, LLM calls, or co-location queries (a controlled
fake location reader supplies the pair so the real graph read/write path is exercised).

Dependencies injected: Neo4j test environment via env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from neo4j import AsyncGraphDatabase

from npc_engine.config import get_settings
from npc_engine.engines.player_model.player_model_engine import PlayerModelEngine
from npc_engine.engines.player_model.player_model_tick import PlayerModelTick
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.character.player_model_writer import get_player_model
from npc_engine.graph.repositories.player_model_repository import Neo4jPlayerModelRepository
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


class _FakeLocationReader:
    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    async def get_collocated_pairs(self) -> list[tuple[str, str]]:
        return self._pairs


async def _create_edge(tx, npc_id: str, player_id: str) -> None:
    await tx.run(
        "MERGE (a:Character {id: $npc_id}) MERGE (b:Character {id: $player_id}) "
        "MERGE (a)-[r:RELATES_TO]->(b) SET r.trust = 70, r.fear = 5, r.affection = 20",
        npc_id=npc_id, player_id=player_id,
    )


async def _cleanup(tx, *ids: str) -> None:
    for node_id in ids:
        await tx.run("MATCH (n {id: $id}) DETACH DELETE n", id=node_id)
        await tx.run("MATCH (pm:PlayerModel {npc_id: $id}) DETACH DELETE pm", id=node_id)


@pytest.mark.asyncio
async def test_player_model_node_updates_on_tick() -> None:
    """run_tick derives and upserts a PlayerModel node readable via get_player_model."""
    uri, user, password = _skip_if_no_neo4j()

    npc_id = _uid("npc")
    player_id = _uid("plr")

    graph_db = GraphDB(get_settings())
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _create_edge(tx, npc_id, player_id)
                await tx.commit()

            adapter = PlayerModelTick(
                engine=PlayerModelEngine(),
                location_reader=_FakeLocationReader([(npc_id, player_id)]),
                relation_reader=Neo4jRelationReadRepository(graph_db),
                model_repo=Neo4jPlayerModelRepository(graph_db),
            )
            result = await adapter.run_tick(tick_id=42)
            record = await get_player_model(session, npc_id=npc_id, player_id=player_id)

        assert len(result["player_models"]) == 1
        assert record is not None
        # composite trust = 70 + 20 - 5 = 85 -> friendly; tick stored as string.
        assert record.perceived_trust == 85
        assert record.perceived_intent == "friendly"
        assert record.last_updated_at == "42"
    finally:
        async with driver.session() as session:
            async with await session.begin_transaction() as tx:
                await _cleanup(tx, npc_id, player_id)
                await tx.commit()
        await driver.close()
        await graph_db.close()
