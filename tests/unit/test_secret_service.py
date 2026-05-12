"""
test_secret_service.py - Unit tests for graph.secret_service and graph.secret_queries.

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
    return TimePoint(year=2, season="winter", day=15, time_of_day="night")


# ---------------------------------------------------------------------------
# create_secret — happy path: returns UUID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_secret_returns_uuid_string():
    session = _make_session()
    with patch("npc_engine.graph.secret_service.uuid.uuid4", return_value="secret-uuid-001"):
        from npc_engine.graph.secret_service import create_secret

        secret_id = await create_secret(
            session,
            character_id="char_1",
            content="The king has a secret heir.",
            severity=80,
            game_time=_make_game_time(),
        )

    assert secret_id == "secret-uuid-001"
    session.begin_transaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_secret_passes_correct_params_to_cypher():
    session = _make_session()
    tx = session.begin_transaction.return_value

    with patch("npc_engine.graph.secret_service.uuid.uuid4", return_value="secret-uuid-002"):
        from npc_engine.graph.secret_service import create_secret

        await create_secret(
            session,
            character_id="char_2",
            content="The tavern keeper is a spy.",
            severity=65,
            game_time=_make_game_time(),
        )

    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args.kwargs
    assert call_kwargs["secret_id"] == "secret-uuid-002"
    assert call_kwargs["content"] == "The tavern keeper is a spy."
    assert call_kwargs["severity"] == 65
    assert call_kwargs["character_id"] == "char_2"


# ---------------------------------------------------------------------------
# get_secrets_for_character — returns list ordered by severity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_secrets_returns_list_for_character():
    fake_records = [
        {"id": "s1", "content": "High secret", "severity": 90, "created_at": "{}"},
        {"id": "s2", "content": "Low secret", "severity": 20, "created_at": "{}"},
    ]

    async def _mock_run(*args, **kwargs):
        async def _records():
            for r in fake_records:
                yield r

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.secret_queries import get_secrets_for_character

    results = await get_secrets_for_character(session, character_id="char_1")
    assert len(results) == 2
    assert results[0]["content"] == "High secret"


# ---------------------------------------------------------------------------
# get_secrets_for_character — no secrets: returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_secrets_returns_empty_list_when_none():
    async def _mock_run(*args, **kwargs):
        async def _records():
            return
            yield

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.secret_queries import get_secrets_for_character

    results = await get_secrets_for_character(session, character_id="char_empty")
    assert results == []


# ---------------------------------------------------------------------------
# get_secrets_for_character — k limit is respected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_secrets_passes_k_limit_to_query():
    captured: list[dict] = []

    async def _mock_run(query: str, **kwargs):
        captured.append(kwargs)

        async def _records():
            return
            yield

        return _records()

    session = MagicMock()
    session.run = _mock_run

    from npc_engine.graph.secret_queries import get_secrets_for_character

    await get_secrets_for_character(session, character_id="char_1", k=5)
    assert captured[0]["k"] == 5


# ---------------------------------------------------------------------------
# get_secrets_for_character_svc — delegates to query layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_secrets_svc_delegates_to_query_layer():
    session = MagicMock()

    with patch(
        "npc_engine.graph.secret_service.get_secrets_for_character",
        new=AsyncMock(return_value=[{"id": "s1", "content": "x", "severity": 50, "created_at": ""}]),
    ) as mock_get:
        from npc_engine.graph.secret_service import get_secrets_for_character_svc

        results = await get_secrets_for_character_svc(session, character_id="char_1", k=2)

    mock_get.assert_awaited_once_with(session, character_id="char_1", k=2)
    assert len(results) == 1
