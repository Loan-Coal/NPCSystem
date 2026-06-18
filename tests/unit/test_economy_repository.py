"""Unit tests for Neo4jEconomyRepository (DEC-122 / SEV-24 Wave 3).

Covers the EconomyGraphPort adapter against a fake GraphDB (session-per-call seam): each
method opens one session and delegates to the matching pricing/transfer graph function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.economy_repository import Neo4jEconomyRepository

_MOD = "npc_engine.graph.repositories.economy_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_read_methods_delegate():
    db = _FakeGraphDB(object())
    repo = Neo4jEconomyRepository(db)  # type: ignore[arg-type]

    with (
        patch(f"{_MOD}.get_character_location_type", new=AsyncMock(return_value="village")) as m_type,
        patch(f"{_MOD}.get_character_location_id", new=AsyncMock(return_value="loc-1")) as m_id,
        patch(f"{_MOD}.get_active_event_types_at_location", new=AsyncMock(return_value=["war"])) as m_ev,
        patch(f"{_MOD}.check_faction_membership", new=AsyncMock(return_value=True)) as m_fac,
    ):
        assert await repo.get_character_location_type(character_id="s1") == "village"
        assert await repo.get_character_location_id(character_id="s1") == "loc-1"
        assert await repo.get_active_event_types_at_location(location_id="loc-1", since_tick=3) == ["war"]
        assert await repo.check_faction_membership(buyer_id="b1", seller_id="s1") is True

    m_type.assert_awaited_once_with(db._session, "s1")
    m_id.assert_awaited_once_with(db._session, "s1")
    m_ev.assert_awaited_once_with(db._session, "loc-1", 3)
    m_fac.assert_awaited_once_with(db._session, "b1", "s1")
    assert db.connect_calls == 4


@pytest.mark.asyncio
async def test_transfer_methods_delegate():
    db = _FakeGraphDB(object())
    repo = Neo4jEconomyRepository(db)  # type: ignore[arg-type]

    with (
        patch(f"{_MOD}.transfer_item_atomic", new=AsyncMock()) as m_item,
        patch(f"{_MOD}.transfer_currency_atomic", new=AsyncMock()) as m_cur,
    ):
        await repo.transfer_item_atomic(
            source_id="s1", destination_id="b1", item_id="i1", quantity=1,
            reason="trade", request_id="rk", idempotency_key="item-rk", transfer_kind="trade",
        )
        await repo.transfer_currency_atomic(
            source_id="b1", destination_id="s1", amount=50, reason="trade",
            request_id="rk", idempotency_key="currency-rk", session_scope="rk", transfer_kind="trade",
        )

    m_item.assert_awaited_once_with(
        db._session, source_id="s1", destination_id="b1", item_id="i1", quantity=1,
        reason="trade", request_id="rk", idempotency_key="item-rk", transfer_kind="trade",
    )
    m_cur.assert_awaited_once_with(
        db._session, source_id="b1", destination_id="s1", amount=50, reason="trade",
        request_id="rk", idempotency_key="currency-rk", session_scope="rk", transfer_kind="trade",
    )
