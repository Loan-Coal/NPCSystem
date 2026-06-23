"""
Tests for graph.skill_service and graph.skill_queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.character.skill_service import (
    add_skill,
    check_skill_threshold_svc,
    get_characters_with_skill_svc,
    get_skills_svc,
    increment_xp,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_iter(rows: list[dict]):
    """Return an async iterable over a list of dicts."""
    class _Iter:
        def __init__(self):
            self._rows = iter(rows)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._rows)
            except StopIteration:
                raise StopAsyncIteration

    return _Iter()


# ---------------------------------------------------------------------------
# add_skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skill_calls_session_run() -> None:
    session = AsyncMock()
    await add_skill(session, character_id="char-1", skill_id="skill-sword", level=10, xp=50)
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["character_id"] == "char-1"
    assert kwargs["skill_id"] == "skill-sword"
    assert kwargs["level"] == 10
    assert kwargs["xp"] == 50


@pytest.mark.asyncio
async def test_add_skill_defaults_xp_to_zero() -> None:
    session = AsyncMock()
    await add_skill(session, character_id="char-1", skill_id="skill-bow", level=5)
    _, kwargs = session.run.call_args
    assert kwargs["xp"] == 0


# ---------------------------------------------------------------------------
# get_skills_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_skills_svc_delegates_to_query() -> None:
    expected = [{"skill_id": "skill-sword", "level": 10, "xp": 50}]
    with patch(
        "npc_engine.graph.character.skill_service.get_skills",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_skills_svc(session, "char-1")
        mock_fn.assert_called_once_with(session, character_id="char-1")
        assert result == expected


@pytest.mark.asyncio
async def test_get_skills_svc_returns_empty_list_when_no_skills() -> None:
    with patch(
        "npc_engine.graph.character.skill_service.get_skills",
        new_callable=AsyncMock,
        return_value=[],
    ):
        session = AsyncMock()
        result = await get_skills_svc(session, "char-nobody")
        assert result == []


# ---------------------------------------------------------------------------
# increment_xp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_increment_xp_returns_new_level() -> None:
    session = AsyncMock()
    record = MagicMock()
    record.__getitem__ = MagicMock(side_effect=lambda k: 5 if k == "new_level" else None)
    session.run.return_value.single = AsyncMock(return_value=record)
    result = await increment_xp(session, character_id="char-1", skill_id="skill-sword", xp_delta=50)
    assert result == 5


@pytest.mark.asyncio
async def test_increment_xp_returns_zero_when_no_record() -> None:
    session = AsyncMock()
    session.run.return_value.single = AsyncMock(return_value=None)
    result = await increment_xp(session, character_id="char-1", skill_id="skill-missing", xp_delta=10)
    assert result == 0


@pytest.mark.asyncio
async def test_increment_xp_passes_tick() -> None:
    session = AsyncMock()
    record = MagicMock()
    record.__getitem__ = MagicMock(side_effect=lambda k: 1 if k == "new_level" else None)
    session.run.return_value.single = AsyncMock(return_value=record)
    await increment_xp(session, character_id="char-1", skill_id="skill-bow", xp_delta=30, tick=99)
    _, kwargs = session.run.call_args
    assert kwargs["tick"] == 99
    assert kwargs["xp_delta"] == 30


# ---------------------------------------------------------------------------
# get_characters_with_skill_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_characters_with_skill_svc_delegates() -> None:
    expected = [{"character_id": "char-1", "character_name": "Alice", "level": 20}]
    with patch(
        "npc_engine.graph.character.skill_service.get_characters_with_skill",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_characters_with_skill_svc(session, "skill-sword", min_level=15)
        mock_fn.assert_called_once_with(session, skill_id="skill-sword", min_level=15)
        assert result == expected


# ---------------------------------------------------------------------------
# check_skill_threshold_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_skill_threshold_svc_returns_true_when_met() -> None:
    with patch(
        "npc_engine.graph.character.skill_service.check_skill_threshold",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_fn:
        session = AsyncMock()
        result = await check_skill_threshold_svc(
            session, character_id="char-1", skill_id="skill-sword", min_level=10
        )
        assert result is True
        mock_fn.assert_called_once_with(
            session, character_id="char-1", skill_id="skill-sword", min_level=10
        )


@pytest.mark.asyncio
async def test_check_skill_threshold_svc_returns_false_when_not_met() -> None:
    with patch(
        "npc_engine.graph.character.skill_service.check_skill_threshold",
        new_callable=AsyncMock,
        return_value=False,
    ):
        session = AsyncMock()
        result = await check_skill_threshold_svc(
            session, character_id="char-1", skill_id="skill-missing", min_level=50
        )
        assert result is False


# ---------------------------------------------------------------------------
# check_skill_threshold (query layer) — no record → False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_skill_threshold_query_no_record_returns_false() -> None:
    session = AsyncMock()
    session.run.return_value.single = AsyncMock(return_value=None)
    from npc_engine.graph.character.skill_queries import check_skill_threshold
    result = await check_skill_threshold(
        session, character_id="char-x", skill_id="skill-x", min_level=1
    )
    assert result is False


@pytest.mark.asyncio
async def test_check_skill_threshold_query_record_true() -> None:
    session = AsyncMock()
    record = MagicMock()
    record.__getitem__ = MagicMock(side_effect=lambda k: True if k == "meets_threshold" else None)
    session.run.return_value.single = AsyncMock(return_value=record)
    from npc_engine.graph.character.skill_queries import check_skill_threshold
    result = await check_skill_threshold(
        session, character_id="char-1", skill_id="skill-sword", min_level=5
    )
    assert result is True
