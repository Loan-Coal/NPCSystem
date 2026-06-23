"""
test_transaction_coordinator.py - Unit tests for the graph/ transaction coordinator (S21.4, DEC-087).

Does NOT: touch a real Neo4j database.

Dependencies injected: None.
"""

from __future__ import annotations

from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.graph.infra.transaction_coordinator import run_in_tx


class _FakeTx:
    """Fake AsyncTransaction recording commit/rollback and supporting `async with`."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.exited = False

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.exited = True
        if exc is not None and not self.committed:
            self.rolled_back = True
        return False


class _FakeSession:
    """Fake AsyncSession yielding a pre-built _FakeTx from begin_transaction."""

    def __init__(self, tx: _FakeTx) -> None:
        self._tx = tx
        self.begin_calls = 0

    async def begin_transaction(self) -> _FakeTx:
        self.begin_calls += 1
        return self._tx


@pytest.mark.asyncio
async def test_run_in_tx_begins_commits_and_returns_work_result() -> None:
    tx = _FakeTx()
    session = _FakeSession(tx=tx)
    seen: list[object] = []

    async def _work(received_tx) -> str:
        seen.append(received_tx)
        return "ok"

    result = await run_in_tx(cast(AsyncSession, session), _work)

    assert result == "ok"
    assert session.begin_calls == 1
    assert seen == [tx]
    assert tx.committed is True
    assert tx.rolled_back is False


@pytest.mark.asyncio
async def test_run_in_tx_rolls_back_and_reraises_original_on_failure() -> None:
    tx = _FakeTx()
    session = _FakeSession(tx=tx)

    class _Boom(RuntimeError):
        pass

    async def _work(_received_tx) -> None:
        raise _Boom("write failed")

    with pytest.raises(_Boom, match="write failed"):
        await run_in_tx(cast(AsyncSession, session), _work)

    assert tx.committed is False
    assert tx.rolled_back is True
