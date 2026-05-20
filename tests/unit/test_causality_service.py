"""
Tests for causality_service and causality_queries.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.causality_service import (
    get_causes_svc,
    get_consequence_chain_svc,
    record_causation,
)


# ---------------------------------------------------------------------------
# record_causation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_causation_calls_run_with_correct_params() -> None:
    session = AsyncMock()
    await record_causation(
        session,
        effect_node_id="event-B",
        effect_node_type="event",
        cause_event_id="event-A",
        causation_strength=90,
        cause_type="direct",
        tick_lag=2,
    )
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["effect_node_id"] == "event-B"
    assert kwargs["cause_event_id"] == "event-A"
    assert kwargs["causation_strength"] == 90
    assert kwargs["cause_type"] == "direct"
    assert kwargs["tick_lag"] == 2


@pytest.mark.asyncio
async def test_record_causation_accepts_quest_node_type() -> None:
    session = AsyncMock()
    await record_causation(
        session,
        effect_node_id="quest-X",
        effect_node_type="quest",
        cause_event_id="event-A",
        causation_strength=80,
        cause_type="narrative",
        tick_lag=0,
    )
    session.run.assert_called_once()


# ---------------------------------------------------------------------------
# get_consequence_chain_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_consequence_chain_passes_params() -> None:
    with patch(
        "npc_engine.graph.causality_service.get_consequence_chain",
        new_callable=AsyncMock,
        return_value=[{"node_id": "event-B", "depth": 1}],
    ) as mock_fn:
        session = AsyncMock()
        result = await get_consequence_chain_svc(
            session, root_event_id="event-A", max_depth=3
        )
        mock_fn.assert_called_once_with(
            session, root_event_id="event-A", max_depth=3
        )
        assert result[0]["node_id"] == "event-B"


@pytest.mark.asyncio
async def test_get_consequence_chain_default_depth() -> None:
    with patch(
        "npc_engine.graph.causality_service.get_consequence_chain",
        new_callable=AsyncMock,
        return_value=[],
    ) as mock_fn:
        session = AsyncMock()
        await get_consequence_chain_svc(session, root_event_id="event-A")
        mock_fn.assert_called_once_with(session, root_event_id="event-A", max_depth=5)


# ---------------------------------------------------------------------------
# get_causes_svc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_causes_passes_node_id() -> None:
    with patch(
        "npc_engine.graph.causality_service.get_causes",
        new_callable=AsyncMock,
        return_value=[{"cause_id": "event-A"}],
    ) as mock_fn:
        session = AsyncMock()
        result = await get_causes_svc(
            session, node_id="event-B", node_type="event"
        )
        mock_fn.assert_called_once_with(
            session, node_id="event-B", node_type="event"
        )
        assert result[0]["cause_id"] == "event-A"


# ---------------------------------------------------------------------------
# Event chain A→B→C integration test (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consequence_chain_returns_b_and_c_for_root_a() -> None:
    chain = [
        {"node_id": "event-B", "depth": 1, "causation": {"cause_id": "event-A"}},
        {"node_id": "event-C", "depth": 2, "causation": {"cause_id": "event-B"}},
    ]
    with patch(
        "npc_engine.graph.causality_service.get_consequence_chain",
        new_callable=AsyncMock,
        return_value=chain,
    ):
        session = AsyncMock()
        result = await get_consequence_chain_svc(session, root_event_id="event-A")
        node_ids = [r["node_id"] for r in result]
        assert "event-B" in node_ids
        assert "event-C" in node_ids
        assert result[0]["depth"] < result[1]["depth"]
