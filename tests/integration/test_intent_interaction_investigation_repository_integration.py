"""
test_intent_interaction_investigation_repository_integration.py — Integration tests for
Neo4jIntentRepository, Neo4jInteractionRepository, and Neo4jInvestigationRepository.

Covers 6 methods T11.2 identified as having no unit-or-integration path. Each method has a
positive-path test that seeds the minimum graph through inline Cypher and asserts the exact
returned values (ids, counts, filtering, field contents); absent-id tests assert exact
empty values (None / [] / 0) only:
  Neo4jIntentRepository: get_player_location, get_unmet_needs, get_unresolved_goals
  Neo4jInteractionRepository: count_player_was_at
  Neo4jInvestigationRepository: get_suspects_for_event, get_witnesses_of_event

Does NOT: test intent scoring, investigation deduction logic, or the HTTP layer.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.graph.repositories.intent_repository import Neo4jIntentRepository
from npc_engine.graph.repositories.interaction_repository import Neo4jInteractionRepository
from npc_engine.graph.repositories.investigation_repository import Neo4jInvestigationRepository


def _make_graph_db() -> GraphDB:
    """Build a GraphDB wired to the eval-stack Neo4j, or skip if env vars are absent."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD required for integration tests")
    settings = Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        NEO4J_URI=uri,
        NEO4J_USER=user,
        NEO4J_PASSWORD=password,
    )
    return GraphDB(settings)


def _uid(prefix: str) -> str:
    """Return a unique, cleanup-safe id with the given prefix."""
    return f"{prefix}-{uuid4().hex[:8]}"


@asynccontextmanager
async def _seeded(cypher: str, ids: list[str], **params: Any) -> AsyncIterator[GraphDB]:
    """Seed the graph with ``cypher``, yield the GraphDB, then DETACH DELETE nodes by ``ids``."""
    graph_db = _make_graph_db()
    try:
        await graph_db.connect()
        async with graph_db.get_session() as session:
            await session.run(cypher, **params)
        yield graph_db
    finally:
        async with graph_db.get_session() as session:
            await session.run("MATCH (n) WHERE n.id IN $ids DETACH DELETE n", ids=ids)
        await graph_db.close()


# ---------------------------------------------------------------------------
# Neo4jIntentRepository
# ---------------------------------------------------------------------------

_SEED_PLAYER_LOCATION = """
CREATE (p:Character {id: $player})-[:LOCATED_AT]->(:Location {id: $loc})
"""


@pytest.mark.asyncio
async def test_get_player_location_returns_none_when_absent() -> None:
    """get_player_location returns None for a player with no LOCATED_AT edge."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        assert await repo.get_player_location(player_id=_uid("player")) is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_player_location_returns_seeded_location_id() -> None:
    """get_player_location returns the id of the Location the player is LOCATED_AT."""
    player, loc = _uid("player"), _uid("loc")
    async with _seeded(_SEED_PLAYER_LOCATION, [player, loc], player=player, loc=loc) as db:
        assert await Neo4jIntentRepository(db).get_player_location(player_id=player) == loc


_SEED_NEEDS = """
CREATE (c:Character {id: $npc})
CREATE (c)-[:NEEDS]->(:Need {id: $n1, kind: 'hunger', level: 0.75, decay_rate: 0.05,
                             character_id: $npc})
CREATE (c)-[:NEEDS]->(:Need {id: $n2, kind: 'rest', level: 0.25, decay_rate: 0.5,
                             character_id: $npc})
CREATE (:Character {id: $other})-[:NEEDS]->(:Need {id: $n3, kind: 'safety', level: 0.5,
                                                   decay_rate: 0.1, character_id: $other})
"""


@pytest.mark.asyncio
async def test_get_unmet_needs_returns_empty_for_unknown_npc() -> None:
    """get_unmet_needs returns exactly [] when the NPC has no Need nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        assert await repo.get_unmet_needs(npc_id=_uid("npc")) == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unmet_needs_returns_only_the_npcs_own_needs() -> None:
    """get_unmet_needs returns the NPC's two Need rows with exact fields, not another NPC's."""
    npc, other = _uid("npc"), _uid("npc")
    n1, n2, n3 = _uid("need"), _uid("need"), _uid("need")
    ids = [npc, other, n1, n2, n3]
    async with _seeded(_SEED_NEEDS, ids, npc=npc, other=other, n1=n1, n2=n2, n3=n3) as db:
        rows = await Neo4jIntentRepository(db).get_unmet_needs(npc_id=npc)
    by_id = {row["id"]: row for row in rows}
    assert len(rows) == 2
    assert by_id[n1] == {
        "id": n1, "kind": "hunger", "level": 0.75, "decay_rate": 0.05, "character_id": npc,
    }
    assert by_id[n2] == {
        "id": n2, "kind": "rest", "level": 0.25, "decay_rate": 0.5, "character_id": npc,
    }


_SEED_GOALS = """
CREATE (c:Character {id: $npc})
CREATE (c)-[:PURSUES]->(:Goal {id: $g1, description: 'find the ledger', urgency: 0.9,
                               status: 'active'})
CREATE (c)-[:PURSUES]->(:Goal {id: $g2, description: 'pay the debt', urgency: 0.4,
                               status: 'complete'})
CREATE (c)-[:PURSUES]->(:Goal {id: $g3, description: 'court the baker', urgency: 0.2,
                               status: 'stalled'})
"""


@pytest.mark.asyncio
async def test_get_unresolved_goals_returns_empty_for_unknown_npc() -> None:
    """get_unresolved_goals returns exactly [] when the NPC has no Goal nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        assert await repo.get_unresolved_goals(npc_id=_uid("npc")) == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unresolved_goals_excludes_complete_goals() -> None:
    """get_unresolved_goals returns active and stalled goals with exact fields, not complete."""
    npc = _uid("npc")
    g1, g2, g3 = _uid("goal"), _uid("goal"), _uid("goal")
    async with _seeded(_SEED_GOALS, [npc, g1, g2, g3], npc=npc, g1=g1, g2=g2, g3=g3) as db:
        rows = await Neo4jIntentRepository(db).get_unresolved_goals(npc_id=npc)
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {g1, g3}
    assert by_id[g1] == {
        "id": g1, "description": "find the ledger", "urgency": 0.9, "status": "active",
    }
    assert by_id[g3] == {
        "id": g3, "description": "court the baker", "urgency": 0.2, "status": "stalled",
    }


# ---------------------------------------------------------------------------
# Neo4jInteractionRepository
# ---------------------------------------------------------------------------

_SEED_WAS_AT = """
CREATE (p:Character {id: $player})
CREATE (a:Location {id: $loc_a})
CREATE (b:Location {id: $loc_b})
CREATE (p)-[:WAS_AT {tick: 1}]->(a)
CREATE (p)-[:WAS_AT {tick: 5}]->(a)
CREATE (p)-[:WAS_AT {tick: 3}]->(b)
"""


@pytest.mark.asyncio
async def test_count_player_was_at_returns_zero_when_no_history() -> None:
    """count_player_was_at returns exactly 0 for a player with no WAS_AT edges."""
    graph_db = _make_graph_db()
    repo = Neo4jInteractionRepository(graph_db)
    try:
        result = await repo.count_player_was_at(
            player_id=_uid("player"), location_id=_uid("loc")
        )
        assert result == 0
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_count_player_was_at_counts_edges_to_the_given_location_only() -> None:
    """count_player_was_at counts 2 WAS_AT edges to loc_a, 1 to loc_b, 0 to an unvisited one."""
    player, loc_a, loc_b, loc_c = _uid("player"), _uid("loc"), _uid("loc"), _uid("loc")
    async with _seeded(
        _SEED_WAS_AT, [player, loc_a, loc_b], player=player, loc_a=loc_a, loc_b=loc_b
    ) as db:
        repo = Neo4jInteractionRepository(db)
        assert await repo.count_player_was_at(player_id=player, location_id=loc_a) == 2
        assert await repo.count_player_was_at(player_id=player, location_id=loc_b) == 1
        assert await repo.count_player_was_at(player_id=player, location_id=loc_c) == 0


# ---------------------------------------------------------------------------
# Neo4jInvestigationRepository
# ---------------------------------------------------------------------------

_SEED_SUSPECTS = """
CREATE (inv:Character {id: $inv, name: 'Inspector'})
CREATE (s1:Character {id: $s1, name: 'Suspect One'})
CREATE (s2:Character {id: $s2, name: 'Suspect Two'})
CREATE (inv)-[:SUSPECTS {event_id: $event, confidence: 0.8}]->(s1)
CREATE (inv)-[:SUSPECTS {event_id: $event, confidence: 0.3}]->(s2)
CREATE (inv)-[:SUSPECTS {event_id: $other_event, confidence: 0.99}]->(s2)
"""


@pytest.mark.asyncio
async def test_get_suspects_for_event_returns_empty_when_absent() -> None:
    """get_suspects_for_event returns exactly [] for a non-existent event."""
    graph_db = _make_graph_db()
    repo = Neo4jInvestigationRepository(graph_db)
    try:
        assert await repo.get_suspects_for_event(event_id=_uid("event")) == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_suspects_for_event_returns_edges_for_that_event_only() -> None:
    """get_suspects_for_event returns both SUSPECTS edges of the event with confidences."""
    inv, s1, s2 = _uid("inv"), _uid("sus"), _uid("sus")
    event, other_event = _uid("event"), _uid("event")
    async with _seeded(
        _SEED_SUSPECTS, [inv, s1, s2], inv=inv, s1=s1, s2=s2,
        event=event, other_event=other_event,
    ) as db:
        repo = Neo4jInvestigationRepository(db)
        rows = await repo.get_suspects_for_event(event_id=event)
        other_rows = await repo.get_suspects_for_event(event_id=other_event)
    by_suspect = {row["suspect"]["id"]: row for row in rows}
    assert len(rows) == 2
    assert set(by_suspect) == {s1, s2}
    assert by_suspect[s1]["confidence"] == 0.8
    assert by_suspect[s2]["confidence"] == 0.3
    assert by_suspect[s1]["suspect"]["name"] == "Suspect One"
    assert all(row["investigator"] == {"id": inv, "name": "Inspector"} for row in rows)
    assert [(r["suspect"]["id"], r["confidence"]) for r in other_rows] == [(s2, 0.99)]


_SEED_WITNESSES = """
CREATE (w1:Character {id: $w1, name: 'Witness One'})
CREATE (w2:Character {id: $w2, name: 'Witness Two'})
CREATE (subj:Character {id: $subj, name: 'Subject'})
CREATE (w1)-[:WITNESSED {event_id: $event, action_type: 'theft', witnessed_at_tick: 42,
                         clarity: 0.9, interpretation: 'saw the theft'}]->(subj)
CREATE (w2)-[:WITNESSED {event_id: $event, action_type: 'flight', witnessed_at_tick: 43,
                         clarity: 0.4, interpretation: 'saw someone run'}]->(subj)
CREATE (w2)-[:WITNESSED {event_id: $other_event, action_type: 'brawl', witnessed_at_tick: 7,
                         clarity: 0.1, interpretation: 'unrelated'}]->(subj)
"""


@pytest.mark.asyncio
async def test_get_witnesses_of_event_returns_empty_when_absent() -> None:
    """get_witnesses_of_event returns exactly [] for a non-existent event."""
    graph_db = _make_graph_db()
    repo = Neo4jInvestigationRepository(graph_db)
    try:
        assert await repo.get_witnesses_of_event(event_id=_uid("event")) == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_witnesses_of_event_returns_edges_for_that_event_only() -> None:
    """get_witnesses_of_event returns both WITNESSED edges with exact edge fields."""
    w1, w2, subj = _uid("wit"), _uid("wit"), _uid("subj")
    event, other_event = _uid("event"), _uid("event")
    async with _seeded(
        _SEED_WITNESSES, [w1, w2, subj], w1=w1, w2=w2, subj=subj,
        event=event, other_event=other_event,
    ) as db:
        rows = await Neo4jInvestigationRepository(db).get_witnesses_of_event(event_id=event)
    by_witness = {row["witness"]["id"]: row for row in rows}
    assert len(rows) == 2
    assert by_witness[w1] == {
        "witness": {"id": w1, "name": "Witness One"},
        "subject": {"id": subj, "name": "Subject"},
        "action_type": "theft",
        "witnessed_at_tick": 42,
        "clarity": 0.9,
        "interpretation": "saw the theft",
    }
    assert by_witness[w2]["action_type"] == "flight"
    assert by_witness[w2]["witnessed_at_tick"] == 43
