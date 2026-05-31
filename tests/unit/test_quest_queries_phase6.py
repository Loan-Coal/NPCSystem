"""
test_quest_queries_phase6.py - Unit tests for quest_queries graph module.

Does NOT: connect to Neo4j. Uses async mock sessions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.quest_queries import get_active_quest_for_player


def _mock_session(records: list[dict]) -> MagicMock:
    result = AsyncMock()
    result.data = AsyncMock(return_value=records)
    session = MagicMock()
    session.run = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_returns_quest_dict_when_active():
    # Queries QuestState nodes with key "qs" (DEC-041: status fix)
    session = _mock_session([
        {"qs": {"quest_id": "q1", "player_id": "player1", "status": "accepted", "title": "Test"}}
    ])
    result = await get_active_quest_for_player(session, player_id="player1")
    assert result is not None
    assert result["quest_id"] == "q1"
    assert result["status"] == "accepted"


@pytest.mark.asyncio
async def test_returns_none_when_no_quest():
    session = _mock_session([])
    result = await get_active_quest_for_player(session, player_id="player1")
    assert result is None


@pytest.mark.asyncio
async def test_passes_player_id_to_query():
    session = _mock_session([])
    await get_active_quest_for_player(session, player_id="player_xyz")
    call_kwargs = session.run.call_args
    params = call_kwargs[1] if call_kwargs[1] else call_kwargs[0][1]
    assert params["player_id"] == "player_xyz"
