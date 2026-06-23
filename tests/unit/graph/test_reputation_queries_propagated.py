"""
test_reputation_queries_propagated.py — Unit tests for get_propagated_reputation_for_npc.

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

    def __aiter__(self):
        return _AsyncIter(self._records)

    async def consume(self) -> None:
        pass


class _FakeSession:
    """Stub session that records the last query and params, returns fixed records."""

    def __init__(self, records: list[dict]) -> None:
        self._records = records
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.last_query = query
        self.last_params = params
        return _FakeResult(self._records)


# ---------------------------------------------------------------------------
# Tests: get_propagated_reputation_for_npc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propagated_rep_returns_list_of_dicts() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    session = _FakeSession([
        {
            "faction_id": "merchants_guild",
            "reputation_delta": 30,
            "account": "player_1 gained standing with merchants_guild (delta=+30)",
            "knowledge_state": "knows",
        }
    ])
    result = await get_propagated_reputation_for_npc(session, npc_id="mira_innkeeper", player_id="player_1")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["faction_id"] == "merchants_guild"
    assert result[0]["reputation_delta"] == 30


@pytest.mark.asyncio
async def test_propagated_rep_returns_empty_when_no_events() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    session = _FakeSession([])
    result = await get_propagated_reputation_for_npc(session, npc_id="mira_innkeeper", player_id="player_1")
    assert result == []


@pytest.mark.asyncio
async def test_propagated_rep_passes_player_id_to_query() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    session = _FakeSession([])
    await get_propagated_reputation_for_npc(session, npc_id="npc_a", player_id="the_player")
    assert session.last_params["player_id"] == "the_player"
    assert session.last_params["npc_id"] == "npc_a"


@pytest.mark.asyncio
async def test_propagated_rep_uses_distorted_account_when_present() -> None:
    """The distorted_summary (gossip version) is preferred over raw summary by coalesce."""
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    distorted = "word is the stranger paid off the whole guild council"
    session = _FakeSession([
        {
            "faction_id": "merchants_guild",
            "reputation_delta": 30,
            "account": distorted,
            "knowledge_state": "rumor",
        }
    ])
    result = await get_propagated_reputation_for_npc(session, npc_id="mira_innkeeper", player_id="player_1")
    assert result[0]["account"] == distorted
    assert result[0]["knowledge_state"] == "rumor"


@pytest.mark.asyncio
async def test_propagated_rep_negative_delta() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    session = _FakeSession([
        {
            "faction_id": "city_guard",
            "reputation_delta": -25,
            "account": "player_1 lost standing with city_guard (delta=-25)",
            "knowledge_state": "knows",
        }
    ])
    result = await get_propagated_reputation_for_npc(session, npc_id="lira_fence", player_id="player_1")
    assert result[0]["reputation_delta"] == -25
    assert result[0]["knowledge_state"] == "knows"


@pytest.mark.asyncio
async def test_propagated_rep_multiple_events() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    rows = [
        {"faction_id": "merchants_guild", "reputation_delta": 30, "account": "...", "knowledge_state": "rumor"},
        {"faction_id": "city_guard", "reputation_delta": -10, "account": "...", "knowledge_state": "knows"},
    ]
    session = _FakeSession(rows)
    result = await get_propagated_reputation_for_npc(session, npc_id="old_henryk", player_id="player_1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_propagated_rep_default_limit_passed() -> None:
    from npc_engine.graph.reputation.reputation_queries import _PROPAGATED_REP_LIMIT, get_propagated_reputation_for_npc

    session = _FakeSession([])
    await get_propagated_reputation_for_npc(session, npc_id="npc_a", player_id="p")
    assert session.last_params["limit"] == _PROPAGATED_REP_LIMIT


@pytest.mark.asyncio
async def test_propagated_rep_custom_limit() -> None:
    from npc_engine.graph.reputation.reputation_queries import get_propagated_reputation_for_npc

    session = _FakeSession([])
    await get_propagated_reputation_for_npc(session, npc_id="npc_a", player_id="p", limit=3)
    assert session.last_params["limit"] == 3
