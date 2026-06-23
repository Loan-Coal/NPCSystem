"""
test_trust_queries.py - Unit tests for trust_queries graph module.

Does NOT: connect to Neo4j. Uses async mock sessions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.relations.trust_queries import get_second_hop_events, get_trust_scores_for_events


def _mock_session(records: list[dict]) -> MagicMock:
    """Build a minimal fake AsyncSession that returns given records."""
    result = AsyncMock()
    result.data = AsyncMock(return_value=records)
    session = MagicMock()
    session.run = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# get_trust_scores_for_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trust_scores_empty_event_ids():
    session = _mock_session([])
    result = await get_trust_scores_for_events(session, npc_id="npc1", event_ids=[])
    assert result == {}
    session.run.assert_not_called()


@pytest.mark.asyncio
async def test_trust_scores_returns_normalized_scores():
    session = _mock_session([
        {"event_id": "e1", "trust_score": 0.8},
        {"event_id": "e2", "trust_score": 0.3},
    ])
    result = await get_trust_scores_for_events(session, npc_id="npc1", event_ids=["e1", "e2"])
    assert result == {"e1": 0.8, "e2": 0.3}


@pytest.mark.asyncio
async def test_trust_scores_clamps_to_zero_one():
    session = _mock_session([
        {"event_id": "e1", "trust_score": 1.5},
        {"event_id": "e2", "trust_score": -0.1},
    ])
    result = await get_trust_scores_for_events(session, npc_id="npc1", event_ids=["e1", "e2"])
    assert result["e1"] == 1.0
    assert result["e2"] == 0.0


@pytest.mark.asyncio
async def test_trust_scores_skips_none_trust():
    session = _mock_session([
        {"event_id": "e1", "trust_score": None},
        {"event_id": "e2", "trust_score": 0.5},
    ])
    result = await get_trust_scores_for_events(session, npc_id="npc1", event_ids=["e1", "e2"])
    assert "e1" not in result
    assert result["e2"] == 0.5


# ---------------------------------------------------------------------------
# get_second_hop_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_hop_returns_event_list():
    session = _mock_session([
        {"e": {"id": "evt1", "summary": "Wagon spotted"}, "trust_weight": 80},
        {"e": {"id": "evt2", "summary": "Meeting at docks"}, "trust_weight": 65},
    ])
    result = await get_second_hop_events(session, npc_id="npc1")
    assert len(result) == 2
    assert result[0]["id"] == "evt1"
    assert result[0]["trust_weight"] == 80
    assert result[1]["trust_weight"] == 65


@pytest.mark.asyncio
async def test_second_hop_empty_when_no_records():
    session = _mock_session([])
    result = await get_second_hop_events(session, npc_id="npc1")
    assert result == []


@pytest.mark.asyncio
async def test_second_hop_passes_threshold_and_limit():
    session = _mock_session([])
    await get_second_hop_events(session, npc_id="npc1", trust_threshold=70, limit=3)
    call_kwargs = session.run.call_args
    params = call_kwargs[1] if call_kwargs[1] else call_kwargs[0][1]
    assert params["trust_threshold"] == 70
    assert params["limit"] == 3
