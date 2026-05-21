"""
test_faction_queries.py - Unit tests for faction read graph functions.

Does NOT: use a real Neo4j connection.

Dependencies injected: fake async session stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from npc_engine.graph.faction_queries import (
    get_controlled_locations,
    get_faction,
    get_factions_for_character,
    get_members_of_faction,
    get_standing,
    list_factions,
    list_standings,
)


# ---------------------------------------------------------------------------
# Fake async stubs
# ---------------------------------------------------------------------------


@dataclass
class _FakeResult:
    _records: list[dict]
    _single_record: dict | None = None

    async def single(self) -> dict | None:
        if self._records:
            return self._records[0]
        return self._single_record

    def __aiter__(self) -> Any:
        return _AsyncIter(self._records)

    async def consume(self) -> None:
        pass


@dataclass
class _AsyncIter:
    _items: list[dict]
    _idx: int = field(default=0, init=False)

    def __aiter__(self) -> "_AsyncIter":
        return self

    async def __anext__(self) -> dict:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _FakeSession:
    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self.calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.calls.append((query, params))
        return self._handler(query, params)


def _make_session_single(record: dict | None) -> _FakeSession:
    """Return a session whose run() always returns a result with one record."""

    def _handler(q: str, p: dict) -> _FakeResult:
        return _FakeResult(_records=[record] if record is not None else [])

    return _FakeSession(handler=_handler)


def _make_session_many(records: list[dict]) -> _FakeSession:
    """Return a session whose run() always returns a result iterable over records."""

    def _handler(q: str, p: dict) -> _FakeResult:
        return _FakeResult(_records=records)

    return _FakeSession(handler=_handler)


# ---------------------------------------------------------------------------
# get_faction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_faction_returns_dict_when_found() -> None:
    record = {"faction": {"id": "f1", "name": "Iron Hand", "archetype": "military", "is_active": True}}
    session = _make_session_single(record)

    result = await get_faction(session, "f1")  # type: ignore[arg-type]

    assert result is not None
    assert result["id"] == "f1"


@pytest.mark.asyncio
async def test_get_faction_returns_none_when_missing() -> None:
    session = _make_session_single(None)

    result = await get_faction(session, "ghost")  # type: ignore[arg-type]

    assert result is None


# ---------------------------------------------------------------------------
# list_factions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_factions_returns_all_when_no_filter() -> None:
    records = [
        {"faction": {"id": "f1", "is_active": True}},
        {"faction": {"id": "f2", "is_active": False}},
    ]
    session = _make_session_many(records)

    result = await list_factions(session)  # type: ignore[arg-type]

    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_factions_returns_empty_list_when_none() -> None:
    session = _make_session_many([])

    result = await list_factions(session)  # type: ignore[arg-type]

    assert result == []


# ---------------------------------------------------------------------------
# get_factions_for_character
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_factions_for_character_returns_faction_and_membership() -> None:
    records = [
        {
            "faction": {"id": "f1", "name": "Iron Hand"},
            "membership": {"role": "member", "status": "active", "joined_at": "2026-01-01"},
        }
    ]
    session = _make_session_many(records)

    result = await get_factions_for_character(session, "char-1")  # type: ignore[arg-type]

    assert len(result) == 1
    assert result[0]["faction"]["id"] == "f1"
    assert result[0]["membership"]["role"] == "member"


@pytest.mark.asyncio
async def test_get_factions_for_character_returns_empty_when_none() -> None:
    session = _make_session_many([])

    result = await get_factions_for_character(session, "char-lonely")  # type: ignore[arg-type]

    assert result == []


# ---------------------------------------------------------------------------
# get_members_of_faction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_members_of_faction_returns_character_and_membership() -> None:
    records = [
        {
            "character": {"id": "c1", "name": "Aldric"},
            "membership": {"role": "leader", "status": "active"},
        },
        {
            "character": {"id": "c2", "name": "Mira"},
            "membership": {"role": "recruit", "status": "active"},
        },
    ]
    session = _make_session_many(records)

    result = await get_members_of_faction(session, "f1")  # type: ignore[arg-type]

    assert len(result) == 2
    assert result[0]["character"]["id"] == "c1"


@pytest.mark.asyncio
async def test_get_members_of_faction_returns_empty_for_unknown_faction() -> None:
    session = _make_session_many([])

    result = await get_members_of_faction(session, "ghost-faction")  # type: ignore[arg-type]

    assert result == []


# ---------------------------------------------------------------------------
# get_standing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_standing_returns_int_when_edge_exists() -> None:
    session = _make_session_single({"standing": -50})

    result = await get_standing(session, "fa", "fb")  # type: ignore[arg-type]

    assert result == -50


@pytest.mark.asyncio
async def test_get_standing_returns_none_when_no_edge() -> None:
    session = _make_session_single(None)

    result = await get_standing(session, "fa", "fb")  # type: ignore[arg-type]

    assert result is None


# ---------------------------------------------------------------------------
# list_standings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_standings_returns_all_directed_edges() -> None:
    records = [
        {"target": {"id": "fb"}, "standing": 80},
        {"target": {"id": "fc"}, "standing": -30},
    ]
    session = _make_session_many(records)

    result = await list_standings(session, "fa")  # type: ignore[arg-type]

    assert len(result) == 2
    assert result[0]["standing"] == 80


@pytest.mark.asyncio
async def test_list_standings_returns_empty_when_no_edges() -> None:
    session = _make_session_many([])

    result = await list_standings(session, "isolated")  # type: ignore[arg-type]

    assert result == []


# ---------------------------------------------------------------------------
# get_controlled_locations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_controlled_locations_returns_location_dicts() -> None:
    records = [
        {"location": {"id": "loc-1", "name": "The Citadel"}},
        {"location": {"id": "loc-2", "name": "East Gate"}},
    ]
    session = _make_session_many(records)

    result = await get_controlled_locations(session, "faction-1")  # type: ignore[arg-type]

    assert len(result) == 2
    assert result[0]["id"] == "loc-1"


@pytest.mark.asyncio
async def test_get_controlled_locations_returns_empty_for_no_control() -> None:
    session = _make_session_many([])

    result = await get_controlled_locations(session, "faction-1")  # type: ignore[arg-type]

    assert result == []
