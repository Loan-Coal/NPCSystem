"""
Module: test_scheme_writer
Layer: tests/unit
Purpose: Unit tests for graph/scheme_writer.py — Cypher targets scheme node +
         EXECUTES_SCHEME/SCHEME_STEP edges. All Neo4j I/O is mocked.
Dependencies: pytest, unittest.mock, npc_engine.graph.scheme_writer
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from npc_engine.graph.scheme_writer import (
    SchemeRecord,
    add_scheme_step,
    get_active_schemes,
    upsert_scheme,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    session = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session, tx


# ---------------------------------------------------------------------------
# upsert_scheme — MERGE scheme node + EXECUTES_SCHEME edge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_scheme_runs_cypher_with_scheme_node_and_edge() -> None:
    """upsert_scheme must issue a Cypher that targets 'scheme' node and
    EXECUTES_SCHEME edge (not any other label/edge).
    """
    session, tx = _make_session()

    await upsert_scheme(
        session=session,
        scheme_id="s1",
        npc_id="aldric",
        goal="corner_grain_market",
        tick=5,
    )

    tx.run.assert_called_once()
    cypher_arg: str = tx.run.call_args[0][0]
    assert "scheme" in cypher_arg.lower() or "Scheme" in cypher_arg
    assert "EXECUTES_SCHEME" in cypher_arg
    tx.commit.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_scheme_passes_correct_params() -> None:
    """upsert_scheme must forward scheme_id, npc_id, goal, and tick."""
    session, tx = _make_session()

    await upsert_scheme(
        session=session,
        scheme_id="s2",
        npc_id="mira",
        goal="run_spy_ring",
        tick=10,
    )

    _, kwargs = tx.run.call_args
    assert kwargs.get("scheme_id") == "s2" or "s2" in tx.run.call_args[0]
    # Validate params dict
    params = {**tx.run.call_args[1]}
    assert params["scheme_id"] == "s2"
    assert params["npc_id"] == "mira"
    assert params["goal"] == "run_spy_ring"


# ---------------------------------------------------------------------------
# add_scheme_step — SCHEME_STEP edge: scheme → event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_scheme_step_creates_scheme_step_edge() -> None:
    """add_scheme_step must issue Cypher containing SCHEME_STEP edge."""
    session, tx = _make_session()

    await add_scheme_step(
        session=session,
        scheme_id="s1",
        event_id="evt_001",
        step_order=1,
        completed=False,
    )

    tx.run.assert_called_once()
    cypher_arg: str = tx.run.call_args[0][0]
    assert "SCHEME_STEP" in cypher_arg
    tx.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_scheme_step_passes_correct_params() -> None:
    """add_scheme_step must pass step_order and completed flags."""
    session, tx = _make_session()

    await add_scheme_step(
        session=session,
        scheme_id="s3",
        event_id="evt_002",
        step_order=2,
        completed=True,
    )

    params = {**tx.run.call_args[1]}
    assert params["scheme_id"] == "s3"
    assert params["event_id"] == "evt_002"
    assert params["step_order"] == 2
    assert params["completed"] is True


# ---------------------------------------------------------------------------
# get_active_schemes — reader for cap enforcement
# ---------------------------------------------------------------------------


class _AsyncIter:
    """Minimal async iterator wrapper for a plain list — used in mocks."""

    def __init__(self, items: list) -> None:
        self._iter = iter(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
async def test_get_active_schemes_returns_empty_list_when_no_rows() -> None:
    """get_active_schemes returns [] when NPC has no active schemes."""
    session = AsyncMock()
    result = _AsyncIter([])
    session.run = AsyncMock(return_value=result)

    records = await get_active_schemes(session=session, npc_id="lira")

    assert records == []


@pytest.mark.asyncio
async def test_get_active_schemes_returns_scheme_records() -> None:
    """get_active_schemes returns SchemeRecord list from graph rows."""
    session = AsyncMock()

    row1 = MagicMock()
    row1.data = MagicMock(
        return_value={
            "s.id": "s1",
            "s.npc_id": "captain_sorn",
            "s.goal": "seize_bridge",
            "s.status": "active",
            "s.created_at_game_time": "tick_1",
        }
    )
    row2 = MagicMock()
    row2.data = MagicMock(
        return_value={
            "s.id": "s2",
            "s.npc_id": "captain_sorn",
            "s.goal": "bribe_council",
            "s.status": "active",
            "s.created_at_game_time": "tick_2",
        }
    )

    result = _AsyncIter([row1, row2])
    session.run = AsyncMock(return_value=result)

    records = await get_active_schemes(session=session, npc_id="captain_sorn")

    assert len(records) == 2
    assert all(isinstance(r, SchemeRecord) for r in records)
    assert records[0].id == "s1"
    assert records[1].goal == "bribe_council"
