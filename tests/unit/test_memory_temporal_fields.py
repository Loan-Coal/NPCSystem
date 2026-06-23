"""
test_memory_temporal_fields.py - Unit tests for the S26.3 event-time memory fields (DEC-094).

Memory gains occurred_at_game_time (when the remembered event happened, distinct from
created_at_game_time = when it was recorded) and is_historical (a prior-era flag). These
let the prompt's past-recollection framing and recency ranking treat old memories correctly.

Does NOT: connect to Neo4j (graph calls mocked; query constants asserted as strings).
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.memory.memory_queries import (
    CYPHER_CREATE_MEMORY,
    CYPHER_GET_MEMORIES_FOR_CHARACTER,
)
from npc_engine.world.time_utils import TimePoint


def _make_session() -> MagicMock:
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def test_create_cypher_sets_temporal_fields() -> None:
    """The create query persists occurred_at_game_time and is_historical."""
    assert "m.occurred_at_game_time = $occurred_at_game_time" in CYPHER_CREATE_MEMORY
    assert "m.is_historical = $is_historical" in CYPHER_CREATE_MEMORY


def test_get_cypher_returns_temporal_fields() -> None:
    """The read query returns occurred_at_game_time and is_historical for age framing."""
    assert "occurred_at_game_time" in CYPHER_GET_MEMORIES_FOR_CHARACTER
    assert "is_historical" in CYPHER_GET_MEMORIES_FOR_CHARACTER


@pytest.mark.asyncio
async def test_create_memory_forwards_historical_event_time() -> None:
    """create_memory forwards occurred_at_game_time + is_historical to the query."""
    session = _make_session()
    captured: list[dict] = []

    async def _run_capture(cypher, **params):
        captured.append(params)
        return AsyncMock()

    session.begin_transaction.return_value.__aenter__.return_value.run = _run_capture

    from npc_engine.graph.memory.memory_service import create_memory

    await create_memory(
        session,
        character_id="old_henryk",
        content="ran dispatches in the last war",
        vividness=92,
        emotional_charge=-80,
        game_time=TimePoint(year=5, season="spring", day=1, time_of_day="morning"),
        occurred_at_game_time=TimePoint(year=1, season="autumn", day=3, time_of_day="night"),
        is_historical=True,
    )

    params = captured[0]
    assert params["is_historical"] is True
    occurred = json.loads(params["occurred_at_game_time"])
    assert occurred["year"] == 1 and occurred["season"] == "autumn"


@pytest.mark.asyncio
async def test_create_memory_defaults_occurred_to_created() -> None:
    """When occurred_at is omitted it defaults to the record time; is_historical False."""
    session = _make_session()
    captured: list[dict] = []

    async def _run_capture(cypher, **params):
        captured.append(params)
        return AsyncMock()

    session.begin_transaction.return_value.__aenter__.return_value.run = _run_capture

    from npc_engine.graph.memory.memory_service import create_memory

    await create_memory(
        session,
        character_id="char_1",
        content="x",
        vividness=50,
        emotional_charge=0,
        game_time=TimePoint(year=3, season="summer", day=2, time_of_day="noon"),
    )

    params = captured[0]
    assert params["is_historical"] is False
    assert params["occurred_at_game_time"] == params["created_at_game_time"]


def test_create_memory_request_accepts_temporal_fields() -> None:
    """CreateMemoryRequest exposes optional occurred_at_game_time + is_historical."""
    from npc_engine.api.routes.knowledge.memories import CreateMemoryRequest

    req = CreateMemoryRequest(
        content="c",
        vividness=10,
        emotional_charge=0,
        occurred_at_game_time={"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"},
        is_historical=True,
    )
    assert req.is_historical is True
    assert req.occurred_at_game_time["year"] == 1

    default = CreateMemoryRequest(content="c", vividness=10, emotional_charge=0)
    assert default.is_historical is False
    assert default.occurred_at_game_time is None
