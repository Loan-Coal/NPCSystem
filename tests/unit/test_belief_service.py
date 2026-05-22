"""
test_belief_service.py - Unit tests for graph.belief_service functions.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

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
# create_belief — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_belief_returns_uuid_string():
    session = _make_session()
    with patch("npc_engine.graph.belief_service.uuid.uuid4", return_value="belief-uuid-001"):
        from npc_engine.graph.belief_service import create_belief

        belief_id = await create_belief(
            session,
            character_id="char_1",
            content="The merchants are not to be trusted.",
            confidence=80,
            game_time=_make_game_time(),
        )

    assert belief_id == "belief-uuid-001"
    session.begin_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_belief_runs_cypher_with_correct_params():
    session = _make_session()
    tx = session.begin_transaction.return_value

    with patch("npc_engine.graph.belief_service.uuid.uuid4", return_value="belief-uuid-002"):
        from npc_engine.graph.belief_service import create_belief

        await create_belief(
            session,
            character_id="char_2",
            content="Rain always brings bad luck.",
            confidence=60,
            game_time=_make_game_time(),
        )

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["belief_id"] == "belief-uuid-002"
    assert call_kwargs["character_id"] == "char_2"
    assert call_kwargs["confidence"] == 60


# ---------------------------------------------------------------------------
# get_beliefs_for_character — returns sorted list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_beliefs_returns_list_sorted_by_confidence():
    fake_records = [
        {"id": "b1", "content": "Merchants lie.", "confidence": 90, "created_at_game_time": "{}"},
        {"id": "b2", "content": "Guards are corrupt.", "confidence": 70, "created_at_game_time": "{}"},
    ]

    async def _mock_run(*args, **kwargs):
        class _R:
            def __aiter__(self):
                async def _gen():
                    for r in fake_records:
                        yield r
                return _gen()

            async def consume(self) -> None:
                pass

        return _R()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.belief_queries import get_beliefs_for_character

    results = await get_beliefs_for_character(session, character_id="char_1", k=5)

    assert len(results) == 2
    assert results[0]["id"] == "b1"
    assert results[1]["id"] == "b2"


@pytest.mark.asyncio
async def test_get_beliefs_returns_empty_list_when_none():
    async def _mock_run(*args, **kwargs):
        class _R:
            def __aiter__(self):
                async def _gen():
                    return
                    yield  # make it an async generator
                return _gen()

            async def consume(self) -> None:
                pass

        return _R()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.belief_queries import get_beliefs_for_character

    results = await get_beliefs_for_character(session, character_id="no_char", k=5)
    assert results == []


# ---------------------------------------------------------------------------
# update_confidence — calls Cypher with correct params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_confidence_calls_cypher():
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.belief_service import update_confidence

    await update_confidence(session, belief_id="belief-uuid-001", new_confidence=55)

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["belief_id"] == "belief-uuid-001"
    assert call_kwargs["confidence"] == 55


# ---------------------------------------------------------------------------
# create_belief — boundary confidence values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_belief_confidence_zero():
    """confidence=0 is at the lower bound and must be passed through unchanged."""
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.belief_service import create_belief

    await create_belief(
        session,
        character_id="char_1",
        content="Absolute uncertainty.",
        confidence=0,
        game_time=_make_game_time(),
    )

    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["confidence"] == 0


@pytest.mark.asyncio
async def test_create_belief_confidence_hundred():
    """confidence=100 is at the upper bound and must be passed through unchanged."""
    session = _make_session()
    tx = session.begin_transaction.return_value

    from npc_engine.graph.belief_service import create_belief

    await create_belief(
        session,
        character_id="char_1",
        content="Absolute certainty.",
        confidence=100,
        game_time=_make_game_time(),
    )

    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["confidence"] == 100


# ---------------------------------------------------------------------------
# get_beliefs_for_character_svc — k boundary values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_beliefs_svc_passes_k_zero():
    """k=0 is forwarded to the query (LIMIT 0 returns empty list)."""
    with patch(
        "npc_engine.graph.belief_service.get_beliefs_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_get:
        from npc_engine.graph.belief_service import get_beliefs_for_character_svc

        result = await get_beliefs_for_character_svc(MagicMock(), character_id="char_1", k=0)

    mock_get.assert_awaited_once_with(ANY, character_id="char_1", k=0)
    assert result == []


@pytest.mark.asyncio
async def test_get_beliefs_svc_k_larger_than_total_returns_all():
    """k=1000 with only 2 beliefs returns the 2 available, not an error."""
    fake_records = [
        {"id": "b1", "content": "A", "confidence": 80},
        {"id": "b2", "content": "B", "confidence": 40},
    ]
    with patch(
        "npc_engine.graph.belief_service.get_beliefs_for_character",
        new_callable=AsyncMock,
        return_value=fake_records,
    ):
        from npc_engine.graph.belief_service import get_beliefs_for_character_svc

        result = await get_beliefs_for_character_svc(MagicMock(), character_id="char_1", k=1000)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_beliefs_svc_returns_empty_for_character_with_no_beliefs():
    with patch(
        "npc_engine.graph.belief_service.get_beliefs_for_character",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from npc_engine.graph.belief_service import get_beliefs_for_character_svc

        result = await get_beliefs_for_character_svc(MagicMock(), character_id="no_beliefs_char", k=5)

    assert result == []
