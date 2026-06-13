"""
Module: test_scheme_writer
Layer: tests/unit
Purpose: Unit tests for graph/scheme_writer.py — Cypher targets scheme node +
         EXECUTES_SCHEME/SCHEME_STEP edges. All Neo4j I/O is mocked.
Dependencies: pytest, unittest.mock, npc_engine.graph.scheme_writer
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.scheme_writer import (
    add_scheme_step,
    mark_scheme_discovered,
    upsert_scheme,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_with_tx() -> tuple[AsyncMock, AsyncMock]:
    """Return (session, tx) where session.begin_transaction() yields the tx."""
    session = AsyncMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session, tx


# Keep old name for backward compatibility with existing tests.
def _make_session() -> tuple[AsyncMock, AsyncMock]:
    return _make_session_with_tx()


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
# mark_scheme_discovered — SEV-01 regression: must use an explicit transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_scheme_discovered_uses_explicit_transaction() -> None:
    """SEV-01: mark_scheme_discovered MUST commit inside an explicit tx, not via
    bare session.run (auto-commit).

    The fix must:
    - Open a transaction on the session (begin_transaction called).
    - Run the Cypher against the tx, not the session directly.
    - Call tx.commit() so the write is durable.
    """
    session, tx = _make_session_with_tx()

    # Arrange: tx.run returns a fake result with one record (scheme found).
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=MagicMock())
    fake_result.consume = AsyncMock()
    tx.run = AsyncMock(return_value=fake_result)

    result = await mark_scheme_discovered(session=session, scheme_id="s_active")

    # Transaction MUST have been opened.
    session.begin_transaction.assert_called_once()
    # Cypher MUST be run on the tx, not directly on the session.
    tx.run.assert_called_once()
    cypher: str = tx.run.call_args[0][0]
    assert "SET" in cypher and "status" in cypher, (
        "Cypher must SET the status field inside the tx"
    )
    # Commit MUST be called (not just rolled back).
    tx.commit.assert_called_once()
    # Return value: True when a record was returned.
    assert result is True


@pytest.mark.asyncio
async def test_mark_scheme_discovered_returns_false_when_not_found() -> None:
    """mark_scheme_discovered returns False when no active scheme matches."""
    session, tx = _make_session_with_tx()

    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=None)
    fake_result.consume = AsyncMock()
    tx.run = AsyncMock(return_value=fake_result)

    result = await mark_scheme_discovered(session=session, scheme_id="no_such_scheme")

    assert result is False
    tx.commit.assert_called_once()


# ---------------------------------------------------------------------------
# SEV-01: add_scheme_step and upsert_scheme accept AsyncTransaction (tx variant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_scheme_step_accepts_tx_param_for_atomic_callers() -> None:
    """SEV-01: add_scheme_step must NOT open its own tx when an external tx is passed.

    Callers that need Event + SCHEME_STEP in one atomic unit must be able to pass
    an AsyncTransaction so both writes land in the same commit.
    """
    tx = AsyncMock()
    tx.run = AsyncMock()

    await add_scheme_step(
        tx=tx,
        scheme_id="s1",
        event_id="ev_x",
        step_order=1,
        completed=True,
    )

    # When tx is provided, it MUST be used directly — no session needed.
    tx.run.assert_called_once()
    cypher: str = tx.run.call_args[0][0]
    assert "SCHEME_STEP" in cypher
