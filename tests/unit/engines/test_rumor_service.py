"""
Unit tests for graph.rumor_service and graph.rumor_queries.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.gossip.rumor_service import (
    believe_rumor,
    create_derived_rumor,
    create_rumor,
    get_rumor_believers_svc,
    get_rumor_tree_svc,
    get_rumors_about_event_svc,
    get_rumors_for_character_svc,
)


# ---------------------------------------------------------------------------
# create_rumor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_rumor_returns_deterministic_id_for_same_event():
    session = AsyncMock()
    id1 = await create_rumor(
        session,
        content="Something happened",
        origin_event_id="event-1",
        created_at_tick=5,
        severity=60,
    )
    id2 = await create_rumor(
        session,
        content="Different wording",
        origin_event_id="event-1",
        created_at_tick=10,
        severity=60,
    )
    assert id1 == id2  # same root rumor for same event


@pytest.mark.asyncio
async def test_create_rumor_different_events_different_ids():
    session = AsyncMock()
    id1 = await create_rumor(
        session, content="A", origin_event_id="event-1", created_at_tick=1, severity=40
    )
    id2 = await create_rumor(
        session, content="B", origin_event_id="event-2", created_at_tick=1, severity=40
    )
    assert id1 != id2


@pytest.mark.asyncio
async def test_create_rumor_no_origin_event_creates_unique_id():
    session = AsyncMock()
    id1 = await create_rumor(
        session, content="Fabricated", origin_event_id=None, created_at_tick=1, severity=20, is_fabricated=True
    )
    id2 = await create_rumor(
        session, content="Another fabricated", origin_event_id=None, created_at_tick=2, severity=20, is_fabricated=True
    )
    assert id1 != id2


@pytest.mark.asyncio
async def test_create_rumor_calls_session_run():
    session = AsyncMock()
    await create_rumor(
        session, content="Test", origin_event_id="evt-1", created_at_tick=3, severity=50
    )
    session.run.assert_called_once()


# ---------------------------------------------------------------------------
# create_derived_rumor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_derived_rumor_returns_uuid():
    session = AsyncMock()
    derived_id = await create_derived_rumor(
        session,
        parent_rumor_id="rumor:root:event-1",
        content="Distorted version",
        mutation_type="exaggeration",
        created_at_tick=7,
    )
    assert isinstance(derived_id, str) and len(derived_id) == 36


@pytest.mark.asyncio
async def test_create_derived_rumor_passes_correct_params():
    session = AsyncMock()
    await create_derived_rumor(
        session,
        parent_rumor_id="parent-id",
        content="Distorted",
        mutation_type="omission",
        created_at_tick=9,
    )
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["parent_rumor_id"] == "parent-id"
    assert call_kwargs["mutation_type"] == "omission"
    assert call_kwargs["created_at_tick"] == 9


# ---------------------------------------------------------------------------
# believe_rumor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_believe_rumor_runs_query():
    session = AsyncMock()
    await believe_rumor(
        session,
        character_id="char-1",
        rumor_id="rumor-1",
        confidence=70,
        tick=5,
        from_character_id="char-2",
    )
    session.run.assert_called_once()
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["character_id"] == "char-1"
    assert call_kwargs["confidence"] == 70
    assert call_kwargs["from_character_id"] == "char-2"


# ---------------------------------------------------------------------------
# Service wrappers (patch query functions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rumors_for_character_svc_delegates():
    expected = [{"id": "r1", "content": "A rumor", "confidence": 75}]
    with patch(
        "npc_engine.graph.gossip.rumor_service.get_rumors_for_character",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_rumors_for_character_svc(session, character_id="c-1", min_confidence=30)
        mock_fn.assert_called_once_with(session, character_id="c-1", min_confidence=30)
        assert result == expected


@pytest.mark.asyncio
async def test_get_rumor_tree_svc_delegates():
    expected = [{"id": "child-1", "depth": 1}]
    with patch(
        "npc_engine.graph.gossip.rumor_service.get_rumor_tree",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_rumor_tree_svc(session, rumor_id="r-1")
        mock_fn.assert_called_once_with(session, rumor_id="r-1")
        assert result == expected


@pytest.mark.asyncio
async def test_get_rumors_about_event_svc_delegates():
    expected = [{"id": "r-1", "content": "A rumor"}]
    with patch(
        "npc_engine.graph.gossip.rumor_service.get_rumors_about_event",
        new_callable=AsyncMock,
        return_value=expected,
    ) as mock_fn:
        session = AsyncMock()
        result = await get_rumors_about_event_svc(session, event_id="evt-1")
        mock_fn.assert_called_once_with(session, event_id="evt-1")
        assert result == expected
