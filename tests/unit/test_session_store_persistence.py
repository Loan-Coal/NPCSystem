"""
Unit tests for SessionStore graph persistence via dialogue_turn nodes (DEC-106 / F3.5).

Covers:
- test_session_round_trip_via_graph: save_to_graph then load_from_graph restores turns
- test_save_swallows_graph_error: a graph error on save is logged and swallowed (not raised)
- test_load_empty_graph_returns_empty: load_from_graph when graph returns no rows leaves store empty
- test_save_caps_at_max_persisted_turns: only the last N turns are persisted per the cap argument
- test_distinct_players_do_not_collide: turns for two players under one NPC stay separate
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.dialogue.session_store import SessionStore


class _FakeResult:
    """Async-iterable stub returning a fixed list of row dicts."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __aiter__(self) -> "_FakeResult":
        self._it = iter(self._rows)
        return self

    async def __anext__(self) -> dict:
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def consume(self) -> None:
        pass


class _FakeSession:
    """In-memory fake that mirrors dialogue_turn node writes so save/load round-trips."""

    def __init__(self) -> None:
        self._store: list[dict] = []

    async def run(self, query: str, **params: object) -> _FakeResult:
        if "DETACH DELETE" in query:
            self._store = [
                r for r in self._store
                if not (r["npc_id"] == params["npc_id"] and r["player_id"] == params["player_id"])
            ]
            return _FakeResult([])
        if "CREATE (t:DialogueTurn" in query:
            for row in params["rows"]:  # type: ignore[union-attr]
                self._store.append({
                    "npc_id": params["npc_id"], "player_id": params["player_id"],
                    "turn_index": row["turn_index"], "role": row["role"], "content": row["content"],
                })
            return _FakeResult([])
        rows = sorted(self._store, key=lambda r: (r["npc_id"], r["player_id"], r["turn_index"]))
        return _FakeResult(rows)


@pytest.mark.asyncio
async def test_session_round_trip_via_graph() -> None:
    """save_to_graph then load_from_graph must restore the same turns (incl. role prefixes)."""
    store = SessionStore(ttl_seconds=3600, max_turns=50)
    await store.append_turns("player1", "npc1", ["player: hello", "npc: world"])

    fake = _FakeSession()
    await store.save_to_graph(session=fake, max_persisted_turns=20)

    fresh = SessionStore(ttl_seconds=3600, max_turns=50)
    await fresh.load_from_graph(session=fake)

    assert await fresh.get_turns("player1", "npc1") == ["player: hello", "npc: world"]


@pytest.mark.asyncio
async def test_save_swallows_graph_error() -> None:
    """A graph error during save_to_graph must be logged and swallowed — must NOT raise."""
    store = SessionStore(ttl_seconds=3600, max_turns=50)
    await store.append_turns("player1", "npc2", ["turn1"])

    broken_session = MagicMock()
    broken_session.run = AsyncMock(side_effect=RuntimeError("neo4j down"))

    await store.save_to_graph(session=broken_session, max_persisted_turns=20)


@pytest.mark.asyncio
async def test_load_empty_graph_returns_empty() -> None:
    """load_from_graph when Neo4j returns no rows must leave the store empty."""
    fresh = SessionStore(ttl_seconds=3600, max_turns=50)
    await fresh.load_from_graph(session=_FakeSession())

    assert await fresh.get_active_npc_ids(min_turns=1) == []


@pytest.mark.asyncio
async def test_save_caps_at_max_persisted_turns() -> None:
    """save_to_graph must only persist the last max_persisted_turns turns."""
    store = SessionStore(ttl_seconds=3600, max_turns=500)
    many_turns = [f"npc: turn-{i}" for i in range(100)]
    await store.append_turns("player1", "npc3", many_turns)

    fake = _FakeSession()
    await store.save_to_graph(session=fake, max_persisted_turns=10)

    fresh = SessionStore(ttl_seconds=3600, max_turns=500)
    await fresh.load_from_graph(session=fake)
    restored = await fresh.get_turns("player1", "npc3")
    assert restored == many_turns[-10:]


@pytest.mark.asyncio
async def test_distinct_players_do_not_collide() -> None:
    """Two players conversing with one NPC keep separate turns (no OQ-9 key collision)."""
    store = SessionStore(ttl_seconds=3600, max_turns=50)
    await store.append_turns("player-one", "npc1", ["player: from one"])
    await store.append_turns("player:two", "npc1", ["player: from two"])

    fake = _FakeSession()
    await store.save_to_graph(session=fake, max_persisted_turns=20)

    fresh = SessionStore(ttl_seconds=3600, max_turns=50)
    await fresh.load_from_graph(session=fake)
    assert await fresh.get_turns("player-one", "npc1") == ["player: from one"]
    assert await fresh.get_turns("player:two", "npc1") == ["player: from two"]
