"""
Tests for location_history_service and location_history_queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.location.location_history_service import (
    get_alibi_window_svc,
    get_location_history_svc,
    prune_location_history,
    record_departure,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(rows: list[dict] | None = None) -> AsyncMock:
    """Return a mock AsyncSession whose run() returns an async-iterable of records."""
    session = AsyncMock()

    if rows is not None:
        records = [MagicMock(**{"data.return_value": r, "__iter__": lambda s: iter(r.items()), "keys": lambda: list(r.keys())}) for r in rows]

        async def _aiter(self):
            for rec in records:
                yield rec

        result_mock = MagicMock()
        result_mock.__aiter__ = _aiter
        # Support dict(record) pattern used in queries
        for i, rec in enumerate(records):
            rec.__iter__ = lambda s, _r=rows[i]: iter(_r.items())
            rec.keys = lambda _r=rows[i]: list(_r.keys())
            rec.__getitem__ = lambda s, k, _r=rows[i]: _r[k]

        session.run.return_value = result_mock

    return session


# ---------------------------------------------------------------------------
# record_departure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_departure_calls_run_with_correct_params() -> None:
    session = AsyncMock()
    await record_departure(
        session,
        character_id="char-1",
        location_id="loc-1",
        arrived_at_tick=5,
        departed_at_tick=10,
        reason="routine",
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["character_id"] == "char-1"
    assert kwargs["location_id"] == "loc-1"
    assert kwargs["arrived_at_tick"] == 5
    assert kwargs["departed_at_tick"] == 10
    assert kwargs["reason"] == "routine"
    assert kwargs["tick_duration"] == 5


@pytest.mark.asyncio
async def test_record_departure_tick_duration_cannot_be_negative() -> None:
    session = AsyncMock()
    await record_departure(
        session,
        character_id="char-1",
        location_id="loc-1",
        arrived_at_tick=10,
        departed_at_tick=5,
        reason="fled",
    )
    _, kwargs = session.run.call_args
    assert kwargs["tick_duration"] == 0


@pytest.mark.asyncio
async def test_record_departure_same_tick_gives_duration_zero() -> None:
    session = AsyncMock()
    await record_departure(
        session,
        character_id="char-1",
        location_id="loc-1",
        arrived_at_tick=7,
        departed_at_tick=7,
        reason="routine",
    )
    _, kwargs = session.run.call_args
    assert kwargs["tick_duration"] == 0


# ---------------------------------------------------------------------------
# get_location_history_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_location_history_passes_limit_to_query() -> None:
    with patch(
        "npc_engine.graph.location.location_history_service.get_location_history",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_location_history_svc(session, character_id="c1", limit=5)
        mock_fn.assert_called_once_with(session, character_id="c1", limit=5)


@pytest.mark.asyncio
async def test_get_location_history_default_limit() -> None:
    with patch(
        "npc_engine.graph.location.location_history_service.get_location_history",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_location_history_svc(session, character_id="c1")
        mock_fn.assert_called_once_with(session, character_id="c1", limit=20)


# ---------------------------------------------------------------------------
# get_alibi_window_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alibi_window_passes_tick_range() -> None:
    with patch(
        "npc_engine.graph.location.location_history_service.get_alibi_window",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_alibi_window_svc(session, character_id="c2", from_tick=10, to_tick=20)
        mock_fn.assert_called_once_with(
            session, character_id="c2", from_tick=10, to_tick=20
        )


# ---------------------------------------------------------------------------
# prune_location_history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prune_location_history_returns_deleted_count() -> None:
    single_mock = AsyncMock(return_value={"deleted": 3})
    result_mock = AsyncMock()
    result_mock.single = single_mock
    session = AsyncMock()
    session.run.return_value = result_mock

    deleted = await prune_location_history(
        session, character_id="c1", older_than_ticks=50
    )
    assert deleted == 3


@pytest.mark.asyncio
async def test_prune_location_history_returns_zero_when_no_rows() -> None:
    result_mock = AsyncMock()
    result_mock.single = AsyncMock(return_value=None)
    session = AsyncMock()
    session.run.return_value = result_mock

    deleted = await prune_location_history(
        session, character_id="c1", older_than_ticks=50
    )
    assert deleted == 0
