"""
test_reputation_queries.py - Unit tests for reputation read functions.

Does NOT: execute graph I/O.

Dependencies injected: None (stub session).
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _AsyncIter:
    def __init__(self, items: list[dict]) -> None:
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


class _FakeResult:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    async def single(self) -> dict | None:
        return self._records[0] if self._records else None

    def __aiter__(self):
        return _AsyncIter(self._records)

    async def consume(self) -> None:
        pass


class _FakeSession:
    def __init__(self, records: list[dict]) -> None:
        self._records = records

    async def run(self, query: str, **params: Any) -> _FakeResult:
        return _FakeResult(self._records)


# ---------------------------------------------------------------------------
# Tests: get_reputation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reputation_returns_dict_when_found() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_reputation

    session = _FakeSession([{"standing": 60, "faction_id": "fac_1", "faction_name": "Guild"}])
    result = await get_reputation(session, character_id="char_1", faction_id="fac_1")
    assert result is not None
    assert result["standing"] == 60


@pytest.mark.asyncio
async def test_get_reputation_returns_none_when_missing() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_reputation

    session = _FakeSession([])
    result = await get_reputation(session, character_id="char_1", faction_id="fac_missing")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: list_reputations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reputations_returns_all_edges() -> None:
    from npc_engine.graph.reputation.reputation_queries import list_reputations

    records = [
        {"faction_id": "fac_1", "faction_name": "Guild", "standing": 40},
        {"faction_id": "fac_2", "faction_name": "Church", "standing": -20},
    ]
    session = _FakeSession(records)
    result = await list_reputations(session, character_id="char_1")
    assert len(result) == 2
    assert result[0]["standing"] == 40
    assert result[1]["faction_id"] == "fac_2"


@pytest.mark.asyncio
async def test_list_reputations_returns_empty_when_no_edges() -> None:
    from npc_engine.graph.reputation.reputation_queries import list_reputations

    session = _FakeSession([])
    result = await list_reputations(session, character_id="char_unknown")
    assert result == []


# ---------------------------------------------------------------------------
# Tests: get_reputation_context_for_npc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reputation_context_returns_items_above_threshold() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_reputation_context_for_npc

    records = [
        {"faction_name": "Guild", "standing": 40},
    ]
    session = _FakeSession(records)
    result = await get_reputation_context_for_npc(
        session, npc_id="npc_1", player_id="player_1", threshold=20
    )
    assert len(result) == 1
    assert result[0]["standing"] == 40
    assert "faction_name" in result[0]
    assert "label" in result[0]


@pytest.mark.asyncio
async def test_get_reputation_context_returns_empty_when_no_factions() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_reputation_context_for_npc

    session = _FakeSession([])
    result = await get_reputation_context_for_npc(
        session, npc_id="npc_1", player_id="player_1", threshold=20
    )
    assert result == []
