"""
Tests for witnessed_service and witnessed_queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.witnessed_service import (
    get_undisclosed_witnesses_svc,
    get_witnessed_by_svc,
    get_witnesses_of_event_svc,
    mark_disclosed,
    record_witness,
)


# ---------------------------------------------------------------------------
# record_witness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_witness_calls_run_with_correct_params() -> None:
    session = AsyncMock()
    await record_witness(
        session,
        witness_id="char-A",
        subject_id="char-B",
        event_id="event-1",
        action_type="stole",
        tick=42,
        clarity=80,
        interpretation="Char B was clearly stealing",
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["witness_id"] == "char-A"
    assert kwargs["subject_id"] == "char-B"
    assert kwargs["event_id"] == "event-1"
    assert kwargs["action_type"] == "stole"
    assert kwargs["witnessed_at_tick"] == 42
    assert kwargs["clarity"] == 80
    assert kwargs["interpretation"] == "Char B was clearly stealing"


@pytest.mark.asyncio
async def test_record_witness_two_witnesses_for_same_event() -> None:
    """Two NPCs at the same location should each get a WITNESSED edge."""
    session = AsyncMock()
    for witness_id in ("char-A", "char-C"):
        await record_witness(
            session,
            witness_id=witness_id,
            subject_id="char-B",
            event_id="event-1",
            action_type="attacked",
            tick=10,
            clarity=70,
            interpretation="Unprovoked attack",
        )
    assert session.run.call_count == 2


# ---------------------------------------------------------------------------
# get_witnesses_of_event_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_witnesses_of_event_passes_event_id() -> None:
    with patch(
        "npc_engine.graph.witnessed_service.get_witnesses_of_event",
        new_callable=AsyncMock,
        return_value=[{"witness_id": "char-A"}],
    ) as mock_fn:
        session = AsyncMock()
        result = await get_witnesses_of_event_svc(session, event_id="ev-1")
        mock_fn.assert_called_once_with(session, event_id="ev-1")
        assert result[0]["witness_id"] == "char-A"


# ---------------------------------------------------------------------------
# get_witnessed_by_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_witnessed_by_passes_subject_and_limit() -> None:
    with patch(
        "npc_engine.graph.witnessed_service.get_witnessed_by",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_witnessed_by_svc(session, subject_id="char-B", limit=5)
        mock_fn.assert_called_once_with(session, subject_id="char-B", limit=5)


# ---------------------------------------------------------------------------
# get_undisclosed_witnesses_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_undisclosed_witnesses_passes_npc_id() -> None:
    with patch(
        "npc_engine.graph.witnessed_service.get_undisclosed_witnesses",
        new_callable=AsyncMock,
        return_value=[{"subject_id": "char-B", "clarity": 80}],
    ) as mock_fn:
        session = AsyncMock()
        result = await get_undisclosed_witnesses_svc(session, npc_id="char-A")
        mock_fn.assert_called_once_with(session, npc_id="char-A")
        assert result[0]["clarity"] == 80


# ---------------------------------------------------------------------------
# mark_disclosed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_disclosed_calls_run_with_correct_params() -> None:
    session = AsyncMock()
    await mark_disclosed(
        session,
        witness_id="char-A",
        subject_id="char-B",
        event_id="event-1",
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["witness_id"] == "char-A"
    assert kwargs["subject_id"] == "char-B"
    assert kwargs["event_id"] == "event-1"
