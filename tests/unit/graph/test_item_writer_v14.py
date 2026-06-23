"""
test_item_writer_v14.py - Unit tests for P3 item transfer writer hardening.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: fake async session/transaction stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.graph.economy.item_writer import CYPHER_APPLY_ITEM_TRANSFER, CYPHER_GRANT_SYSTEM_ITEM, transfer_item_atomic
from npc_engine.utils.errors import ItemTransferValidationError, NodeNotFoundError


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
async def test_transfer_item_atomic_replays_without_second_write() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return {"request_id": "req-existing", "item_id": "item-1", "quantity": 1}
        if query in {CYPHER_APPLY_ITEM_TRANSFER, CYPHER_GRANT_SYSTEM_ITEM}:
            raise AssertionError("item apply query should not execute for replay")
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    result = await transfer_item_atomic(
        session=cast(AsyncSession, session),
        source_id="source-1",
        destination_id="destination-1",
        item_id="item-1",
        quantity=1,
        reason="quest_reward",
        request_id="req-1",
        idempotency_key="idem-1",
        transfer_kind="quest_reward",
    )

    assert result.replayed is True
    assert result.request_id == "req-existing"
    assert result.item_id == "item-1"


@pytest.mark.asyncio
async def test_transfer_item_atomic_uses_system_grant_query_for_quest_reward() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return None
        if query == CYPHER_GRANT_SYSTEM_ITEM:
            return {"item_id": params["item_id"], "quantity": params["quantity"]}
        if query == CYPHER_APPLY_ITEM_TRANSFER:
            raise AssertionError("normal apply query should not execute for system quest reward")
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    result = await transfer_item_atomic(
        session=cast(AsyncSession, session),
        source_id="system",
        destination_id="player-1",
        item_id="reward-satchel",
        quantity=2,
        reason="quest_reward:quest-1",
        request_id="req-1",
        idempotency_key="idem-1",
        transfer_kind="quest_reward",
    )

    assert result.replayed is False
    assert result.item_id == "reward-satchel"
    assert result.quantity == 2
    assert tx.committed is True


def test_system_grant_query_includes_with_between_merge_and_match() -> None:
    normalized_query = " ".join(CYPHER_GRANT_SYSTEM_ITEM.split())

    merge_pos = normalized_query.find("MERGE (src:Character {id: $source_id})")
    with_pos = normalized_query.find("WITH src")
    match_dst_pos = normalized_query.find("MATCH (dst:Character {id: $destination_id})")

    assert merge_pos != -1
    assert with_pos != -1
    assert match_dst_pos != -1
    assert merge_pos < with_pos < match_dst_pos


@pytest.mark.asyncio
async def test_transfer_item_atomic_raises_not_found_when_source_missing() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return None
        if query == CYPHER_APPLY_ITEM_TRANSFER:
            return None
        if "MATCH (c:Character {id: $character_id}) RETURN c.id AS id" in query and params["character_id"] == "source-1":
            return None
        if "MATCH (c:Character {id: $character_id}) RETURN c.id AS id" in query and params["character_id"] == "destination-1":
            return {"id": "destination-1"}
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    with pytest.raises(NodeNotFoundError):
        await transfer_item_atomic(
            session=cast(AsyncSession, session),
            source_id="source-1",
            destination_id="destination-1",
            item_id="item-1",
            quantity=1,
            reason="trade",
            request_id="req-1",
            idempotency_key="idem-1",
            transfer_kind="trade_item",
        )


@pytest.mark.asyncio
async def test_transfer_item_atomic_raises_validation_error_when_guards_fail() -> None:
    def _query_handler(query: str, params: dict) -> dict | None:
        if "idempotency_key" in query and "LIMIT 1" in query:
            return None
        if query == CYPHER_APPLY_ITEM_TRANSFER:
            return None
        if "MATCH (c:Character {id: $character_id}) RETURN c.id AS id" in query:
            return {"id": params["character_id"]}
        return None

    tx = _FakeTx(query_handler=_query_handler)
    session = _FakeSession(tx=tx)

    with pytest.raises(ItemTransferValidationError):
        await transfer_item_atomic(
            session=cast(AsyncSession, session),
            source_id="source-1",
            destination_id="destination-1",
            item_id="item-1",
            quantity=1,
            reason="trade",
            request_id="req-1",
            idempotency_key="idem-1",
            transfer_kind="trade_item",
        )
