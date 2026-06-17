"""
Module: test_scheming_repository
Layer: tests/unit
Purpose: Unit tests for graph/repositories/scheming_repository.py — verifies
         Neo4jSchemingRepository delegates to scheme_reader/writer, graph_reader,
         and event_writer correctly. Uses a fake GraphDB with a mock session.
Dependencies: pytest, unittest.mock
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.repositories.scheming_repository import Neo4jSchemingRepository
from npc_engine.graph.scheme_reader import ActiveSchemeProgress, SchemeRecord


# ---------------------------------------------------------------------------
# Fake GraphDB
# ---------------------------------------------------------------------------


class _FakeGraphDB:
    def __init__(self) -> None:
        self.session = AsyncMock()

    async def connect(self) -> None:
        return None

    @asynccontextmanager
    async def get_session(self):
        yield self.session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_schemes_delegates() -> None:
    db = _FakeGraphDB()
    repo = Neo4jSchemingRepository(graph_db=db)
    expected = [SchemeRecord(id="s1", npc_id="lira", goal="rob_vault", status="active")]

    with patch(
        "npc_engine.graph.repositories.scheming_repository.get_active_schemes",
        new=AsyncMock(return_value=expected),
    ) as mock_fn:
        result = await repo.get_active_schemes("lira")

    assert result == expected
    mock_fn.assert_called_once_with(db.session, "lira")


@pytest.mark.asyncio
async def test_upsert_scheme_delegates() -> None:
    db = _FakeGraphDB()
    repo = Neo4jSchemingRepository(graph_db=db)

    with patch(
        "npc_engine.graph.repositories.scheming_repository.upsert_scheme",
        new=AsyncMock(),
    ) as mock_fn:
        await repo.upsert_scheme(scheme_id="s1", npc_id="lira", goal="rob", tick=5)

    mock_fn.assert_called_once_with(session=db.session, scheme_id="s1", npc_id="lira", goal="rob", tick=5)


@pytest.mark.asyncio
async def test_get_all_active_schemes_with_steps_delegates() -> None:
    db = _FakeGraphDB()
    repo = Neo4jSchemingRepository(graph_db=db)
    expected = [ActiveSchemeProgress(scheme_id="s1", npc_id="lira", goal="rob", step_count=2)]

    with patch(
        "npc_engine.graph.repositories.scheming_repository.get_all_active_schemes_with_steps",
        new=AsyncMock(return_value=expected),
    ) as mock_fn:
        result = await repo.get_all_active_schemes_with_steps()

    assert result == expected
    mock_fn.assert_called_once_with(db.session)


@pytest.mark.asyncio
async def test_get_npc_location_id_delegates() -> None:
    db = _FakeGraphDB()
    repo = Neo4jSchemingRepository(graph_db=db)

    with patch(
        "npc_engine.graph.repositories.scheming_repository.get_npc_location_id",
        new=AsyncMock(return_value="tavern"),
    ) as mock_fn:
        result = await repo.get_npc_location_id("lira")

    assert result == "tavern"
    mock_fn.assert_called_once_with(db.session, "lira")


@pytest.mark.asyncio
async def test_emit_scheme_step_atomic_runs_in_tx() -> None:
    """emit_scheme_step_atomic must call run_in_tx to keep the two writes atomic."""
    db = _FakeGraphDB()
    repo = Neo4jSchemingRepository(graph_db=db)
    tx_call_count: list[int] = [0]

    async def _fake_run_in_tx(session: Any, fn: Any) -> None:
        tx_call_count[0] += 1
        fake_tx = MagicMock()
        await fn(fake_tx)

    with (
        patch(
            "npc_engine.graph.repositories.scheming_repository.run_in_tx",
            side_effect=_fake_run_in_tx,
        ),
        patch(
            "npc_engine.graph.repositories.scheming_repository.upsert_event",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.graph.repositories.scheming_repository.add_scheme_step",
            new=AsyncMock(),
        ),
    ):
        await repo.emit_scheme_step_atomic(
            event={"id": "evt1"},
            scheme_id="s1",
            event_id="evt1",
            step_order=1,
            completed=True,
        )

    assert tx_call_count[0] == 1, "run_in_tx must be called exactly once"
