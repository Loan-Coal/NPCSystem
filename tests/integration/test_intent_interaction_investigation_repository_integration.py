"""
test_intent_interaction_investigation_repository_integration.py — Integration tests for
Neo4jIntentRepository, Neo4jInteractionRepository, and Neo4jInvestigationRepository.

Covers 6 methods T11.2 identified as having no unit-or-integration path:
  Neo4jIntentRepository: get_player_location, get_unmet_needs, get_unresolved_goals
  Neo4jInteractionRepository: count_player_was_at
  Neo4jInvestigationRepository: get_suspects_for_event, get_witnesses_of_event

Does NOT: test intent scoring, investigation deduction logic, or the HTTP layer.

Dependencies injected: eval-stack Neo4j via NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
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


@pytest.mark.asyncio
async def test_get_player_location_returns_none_when_absent() -> None:
    """get_player_location returns None for a player with no LOCATED_AT edge."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        result = await repo.get_player_location(player_id=f"player-{uuid4()}")
        assert result is None
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unmet_needs_returns_empty_for_unknown_npc() -> None:
    """get_unmet_needs returns an empty list when the NPC has no Need nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        result = await repo.get_unmet_needs(npc_id=f"npc-{uuid4()}")
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_unresolved_goals_returns_empty_for_unknown_npc() -> None:
    """get_unresolved_goals returns an empty list when the NPC has no Goal nodes."""
    graph_db = _make_graph_db()
    repo = Neo4jIntentRepository(graph_db)
    try:
        result = await repo.get_unresolved_goals(npc_id=f"npc-{uuid4()}")
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_count_player_was_at_returns_zero_when_no_history() -> None:
    """count_player_was_at returns 0 for a player with no WAS_AT edges."""
    graph_db = _make_graph_db()
    repo = Neo4jInteractionRepository(graph_db)
    try:
        result = await repo.count_player_was_at(
            player_id=f"player-{uuid4()}", location_id=f"loc-{uuid4()}"
        )
        assert result == 0
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_suspects_for_event_returns_empty_when_absent() -> None:
    """get_suspects_for_event returns an empty list for a non-existent event."""
    graph_db = _make_graph_db()
    repo = Neo4jInvestigationRepository(graph_db)
    try:
        result = await repo.get_suspects_for_event(event_id=f"event-{uuid4()}")
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()


@pytest.mark.asyncio
async def test_get_witnesses_of_event_returns_empty_when_absent() -> None:
    """get_witnesses_of_event returns an empty list for a non-existent event."""
    graph_db = _make_graph_db()
    repo = Neo4jInvestigationRepository(graph_db)
    try:
        result = await repo.get_witnesses_of_event(event_id=f"event-{uuid4()}")
        assert isinstance(result, list)
        assert result == []
    finally:
        await graph_db.close()
