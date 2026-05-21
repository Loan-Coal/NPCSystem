"""
test_currency_writer_v14.py - Unit tests for P2 atomic currency graph writes.

Does NOT: use a real Neo4j connection.

Dependencies injected: fake async session/transaction stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.graph.currency_writer import (
    CYPHER_APPLY_SYSTEM_REWARD_TRANSFER,
    CYPHER_APPLY_TRANSFER,
    transfer_currency_atomic,
)
from npc_engine.utils.errors import CurrencyInsufficientFundsError


@dataclass
class _FakeResult:
    record: dict | None

    async def single(self):
        return self.record

    async def consume(self) -> None:
        pass


class _FakeTx:
    def __init__(self, query_handler):
        self._query_handler = query_handler
        self.run_calls: list[tuple[str, dict]] = []
        self.committed = False

    async def run(self, query: str, **params):
        self.run_calls.append((query, params))
        return _FakeResult(record=self._query_handler(query, params))

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, tx: _FakeTx):
        self._tx = tx

    async def begin_transaction(self):
        return self._tx


@pytest.mark.asyncio
async def test_transfer_currency_atomic_applies_debit_credit_with_audit_edge() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return None
        if query == CYPHER_APPLY_TRANSFER:
            return {"source_balance": 75, "destination_balance": 125}
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    result = await transfer_currency_atomic(
        session=cast(AsyncSession, session),
        source_id="player",
        destination_id="shop",
        amount=25,
        reason="buy",
        request_id="req-1",
        idempotency_key="idem-1",
        session_scope="s1",
        transfer_kind="buy_item",
    )

    assert result.replayed is False
    assert result.source_balance == 75
    assert result.destination_balance == 125
    assert tx.committed is True
    apply_queries = [query for query, _ in tx.run_calls if query == CYPHER_APPLY_TRANSFER]
    assert len(apply_queries) == 1
    assert "coalesce(src.currency_balance, 0) >= $amount" in apply_queries[0]
    assert "CREATE (src)-[:TRANSFERRED_TO" in apply_queries[0]


@pytest.mark.asyncio
async def test_transfer_currency_atomic_raises_insufficient_funds_when_guard_fails() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return None
        if query == CYPHER_APPLY_TRANSFER:
            return None
        if "MATCH (c:Character {id: $character_id})" in query and params["character_id"] == "player":
            return {"balance": 5}
        if "MATCH (c:Character {id: $character_id})" in query and params["character_id"] == "shop":
            return {"balance": 100}
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    with pytest.raises(CurrencyInsufficientFundsError):
        await transfer_currency_atomic(
            session=cast(AsyncSession, session),
            source_id="player",
            destination_id="shop",
            amount=25,
            reason="buy",
            request_id="req-1",
            idempotency_key="idem-1",
            session_scope="s1",
            transfer_kind="buy_item",
        )


@pytest.mark.asyncio
async def test_transfer_currency_atomic_replays_without_second_debit_credit() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return {
                "request_id": "req-existing",
                "amount": 25,
                "source_balance": 75,
                "destination_balance": 125,
            }
        if query == CYPHER_APPLY_TRANSFER:
            raise AssertionError("apply transfer query should not execute for replay")
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    result = await transfer_currency_atomic(
        session=cast(AsyncSession, session),
        source_id="player",
        destination_id="shop",
        amount=25,
        reason="buy",
        request_id="req-1",
        idempotency_key="idem-1",
        session_scope="s1",
        transfer_kind="buy_item",
    )

    assert result.replayed is True
    assert result.request_id == "req-existing"


def test_system_reward_currency_query_includes_with_between_merge_and_match() -> None:
    normalized_query = " ".join(CYPHER_APPLY_SYSTEM_REWARD_TRANSFER.split())

    merge_pos = normalized_query.find("MERGE (src:Character {id: $source_id})")
    with_pos = normalized_query.find("WITH src")
    match_dst_pos = normalized_query.find("MATCH (dst:Character {id: $destination_id})")

    assert merge_pos != -1
    assert with_pos != -1
    assert match_dst_pos != -1
    assert merge_pos < with_pos < match_dst_pos
