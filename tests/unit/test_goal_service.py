"""
test_goal_service.py - Unit tests for graph.goal_service functions.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.world.time_utils import TimePoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock behaving like an AsyncSession with a transaction."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def _make_game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=3, time_of_day="morning")


# ---------------------------------------------------------------------------
# create_goal — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_goal_returns_uuid_string():
    session = _make_session()
    with patch("npc_engine.graph.goal_service.uuid.uuid4", return_value="goal-uuid-001"):
        from npc_engine.graph.goal_service import create_goal

        goal_id = await create_goal(
            session,
            character_id="char_1",
            description="Find the missing merchant.",
            urgency=75,
            game_time=_make_game_time(),
        )

    assert goal_id == "goal-uuid-001"
    session.begin_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_goal_runs_cypher_with_correct_params():
    session = _make_session()
    tx = session.begin_transaction.return_value

    with patch("npc_engine.graph.goal_service.uuid.uuid4", return_value="goal-uuid-002"):
        from npc_engine.graph.goal_service import create_goal

        await create_goal(
            session,
            character_id="char_2",
            description="Protect the village elder.",
            urgency=90,
            game_time=_make_game_time(),
            target_id="npc_elder_01",
        )

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["goal_id"] == "goal-uuid-002"
    assert call_kwargs["character_id"] == "char_2"
    assert call_kwargs["urgency"] == 90
    assert call_kwargs["status"] == "active"
    assert call_kwargs["target_id"] == "npc_elder_01"


# ---------------------------------------------------------------------------
# get_goals_for_character — returns list sorted by urgency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_goals_returns_list_sorted_by_urgency():
    fake_records = [
        {
            "id": "g1",
            "description": "Find the key.",
            "urgency": 90,
            "status": "active",
            "created_at_game_time": "{}",
            "target_id": "",
        },
        {
            "id": "g2",
            "description": "Warn the guard.",
            "urgency": 60,
            "status": "active",
            "created_at_game_time": "{}",
            "target_id": "",
        },
    ]

    async def _mock_run(*args, **kwargs):
        async def _records():
            for r in fake_records:
                yield r

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.goal_queries import get_goals_for_character

    results = await get_goals_for_character(session, character_id="char_1", k=5)

    assert len(results) == 2
    assert results[0]["id"] == "g1"
    assert results[1]["id"] == "g2"


@pytest.mark.asyncio
async def test_get_goals_with_status_filter():
    fake_records = [
        {
            "id": "g3",
            "description": "Achieved goal.",
            "urgency": 50,
            "status": "achieved",
            "created_at_game_time": "{}",
            "target_id": "",
        }
    ]

    async def _mock_run(*args, **kwargs):
        # Verify the status_filter param was passed
        assert kwargs.get("status_filter") == "achieved"

        async def _records():
            for r in fake_records:
                yield r

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.goal_queries import get_goals_for_character

    results = await get_goals_for_character(
        session, character_id="char_1", k=5, status_filter="achieved"
    )

    assert len(results) == 1
    assert results[0]["status"] == "achieved"


@pytest.mark.asyncio
async def test_get_goals_returns_empty_list_when_none():
    async def _mock_run(*args, **kwargs):
        async def _records():
            return
            yield  # make it an async generator

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.goal_queries import get_goals_for_character

    results = await get_goals_for_character(session, character_id="no_char", k=5)
    assert results == []


# ---------------------------------------------------------------------------
# update_goal_status — calls Cypher with correct params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_goal_status_calls_cypher():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.goal_service import update_goal_status

    await update_goal_status(session, goal_id="goal-uuid-001", new_status="achieved")

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["goal_id"] == "goal-uuid-001"
    assert call_kwargs["status"] == "achieved"
