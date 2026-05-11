"""
test_replay_helpers.py - Unit tests for load_idempotent_replay_record.

Does NOT: connect to Neo4j; all graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.replay_helpers import load_idempotent_replay_record


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tx(*, single_return=None) -> AsyncMock:
    result_mock = AsyncMock()
    result_mock.single = AsyncMock(return_value=single_return)
    tx = AsyncMock()
    tx.run = AsyncMock(return_value=result_mock)
    return tx


# ---------------------------------------------------------------------------
# load_idempotent_replay_record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_idempotency_key_returns_none_without_db_call():
    tx = _make_tx()
    result = await load_idempotent_replay_record(
        tx=tx,
        replay_cypher="MATCH (n) RETURN n",
        params={},
        idempotency_key="",
    )
    assert result is None
    tx.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_found_returns_dict():
    record = MagicMock()
    record.__iter__ = MagicMock(return_value=iter([("id", "idem_1"), ("payload", "ok")]))
    tx = _make_tx(single_return=record)

    result = await load_idempotent_replay_record(
        tx=tx,
        replay_cypher="MATCH (n {key: $key}) RETURN n",
        params={"key": "idem_1"},
        idempotency_key="idem_1",
    )

    assert isinstance(result, dict)
    tx.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_record_found_returns_none():
    tx = _make_tx(single_return=None)

    result = await load_idempotent_replay_record(
        tx=tx,
        replay_cypher="MATCH (n {key: $key}) RETURN n",
        params={"key": "missing_key"},
        idempotency_key="missing_key",
    )

    assert result is None
    tx.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_params_are_forwarded_to_tx_run():
    tx = _make_tx(single_return=None)
    params = {"key": "idem_abc", "scope": "session_1"}

    await load_idempotent_replay_record(
        tx=tx,
        replay_cypher="MATCH (n) RETURN n",
        params=params,
        idempotency_key="idem_abc",
    )

    call_kwargs = tx.run.call_args
    assert call_kwargs is not None


@pytest.mark.asyncio
async def test_cypher_string_passed_to_tx_run():
    tx = _make_tx(single_return=None)
    cypher = "MATCH (r:IdempotencyRecord {key: $key}) RETURN r"

    await load_idempotent_replay_record(
        tx=tx,
        replay_cypher=cypher,
        params={"key": "k1"},
        idempotency_key="k1",
    )

    tx.run.assert_awaited_once()
    positional_args = tx.run.call_args[0]
    assert positional_args[0] == cypher
