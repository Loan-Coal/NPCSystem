"""
test_gossip_event_choice_integration.py - A sharer tells a receiver something it does not know yet.

T25.12: CYPHER_BATCH_EVENT_TRUST picked the sharer's canonical, newest event whatever the receiver
knew. On the demo seed every NPC knows the same public event, so every pair re-told it, the MERGE
rewrote an existing edge, and the war rumour never left Mira (live run, 2026-11-16).

Does NOT: run the gossip handler, the RNG gate, or the distortion step.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.gossip_repository import Neo4jGossipRepository

_SETUP = """
CREATE (s:Character {id: $sharer}), (r:Character {id: $receiver}),
       (known:Event {id: $known, is_canonical: true, occurred_at: '2026-01-02', summary: 'known', severity: 10}),
       (fresh:Event {id: $fresh, is_canonical: false, occurred_at: '2026-01-01', summary: 'fresh', severity: 70}),
       (s)-[:KNOWS_ABOUT {knowledge_state: 'knows', distortion_level: 0}]->(known),
       (s)-[:KNOWS_ABOUT {knowledge_state: 'rumor', distortion_level: 20}]->(fresh),
       (r)-[:KNOWS_ABOUT {knowledge_state: 'knows', distortion_level: 0}]->(known)
"""


def _make_graph_db() -> GraphDB:
    """Build a GraphDB wired to the eval-stack Neo4j, or skip if env vars are absent."""
    uri, user, password = (os.getenv(k) for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"))
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    return GraphDB(Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        NEO4J_URI=uri, NEO4J_USER=user, NEO4J_PASSWORD=password,
    ))


@pytest.mark.asyncio
async def test_sharer_prefers_an_event_the_receiver_does_not_know() -> None:
    """The fresh event wins over the canonical, newer event the receiver already holds."""
    graph_db = _make_graph_db()
    ids = {name: f"{name}-test-{uuid4().hex[:8]}" for name in ("sharer", "receiver", "known", "fresh")}
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(_SETUP, **ids)

        rows = await Neo4jGossipRepository(graph_db).select_batch_event_trust(
            [{"sharer_id": ids["sharer"], "receiver_id": ids["receiver"]}]
        )

        assert [row["event_id"] for row in rows] == [ids["fresh"]]
        assert rows[0]["sharer_distortion_level"] == 20
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=list(ids.values()))
        await graph_db.close()


@pytest.mark.asyncio
async def test_sharer_still_retells_when_the_receiver_knows_everything() -> None:
    """Preferring new events must not stop a pair whose receiver already knows them all."""
    graph_db = _make_graph_db()
    ids = {name: f"{name}-test-{uuid4().hex[:8]}" for name in ("sharer", "receiver", "known", "fresh")}
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(_SETUP, **ids)
            await session.run(
                "MATCH (r:Character {id: $receiver}), (f:Event {id: $fresh}) "
                "CREATE (r)-[:KNOWS_ABOUT {knowledge_state: 'rumor'}]->(f)",
                receiver=ids["receiver"], fresh=ids["fresh"],
            )

        rows = await Neo4jGossipRepository(graph_db).select_batch_event_trust(
            [{"sharer_id": ids["sharer"], "receiver_id": ids["receiver"]}]
        )

        assert [row["event_id"] for row in rows] == [ids["known"]]
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=list(ids.values()))
        await graph_db.close()
