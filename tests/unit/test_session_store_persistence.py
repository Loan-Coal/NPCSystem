"""
Unit tests for SessionStore graph persistence (EXP-230 slice-1).

Covers:
- test_session_round_trip_via_graph: save_to_graph then load_from_graph restores turns
- test_save_swallows_graph_error: a graph error on save is logged and swallowed (not raised)
- test_load_empty_graph_returns_empty: load_from_graph when graph returns no rows leaves store empty
- test_save_caps_at_max_persisted_turns: only last N turns are written per the cap argument
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.session_store import SessionStore


# ---------------------------------------------------------------------------
# Fake Neo4j session helpers
# ---------------------------------------------------------------------------

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


class _NodeLike(dict):
    """Dict subclass that also behaves like a Neo4j node (supports dict())."""


class _FakeSession:
    """Stateful fake Neo4j session that records writes and serves configurable reads."""

    def __init__(self) -> None:
        self.written_calls: list[dict] = []
        self._read_rows: list[dict] = []

    def set_read_rows(self, rows: list[dict]) -> None:
        """Configure the rows that the next read query will return."""
        self._read_rows = rows

    async def run(self, query: str, **params: object) -> _FakeResult:
        if "SET" in query or "MERGE" in query:
            self.written_calls.append(dict(params))
            return _FakeResult([])
        # read query
        return _FakeResult(self._read_rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_round_trip_via_graph() -> None:
    """save_to_graph then load_from_graph must restore the same turns."""
    store = SessionStore(ttl_seconds=3600, max_turns=50)
    await store.append_turns("player1", "npc1", ["hello", "world"])

    fake_session = _FakeSession()

    # Save
    max_turns = 20
    await store.save_to_graph(session=fake_session, max_persisted_turns=max_turns)

    # Verify something was written
    assert fake_session.written_calls, "Expected at least one write call"

    # Build a synthetic read result that mirrors what Neo4j would return
    from npc_engine.graph.session_persistence import make_prop_key
    prop_key = make_prop_key("player1")
    node = _NodeLike({"id": "npc1", prop_key: json.dumps(["hello", "world"])})
    fake_session.set_read_rows([{"c": node}])

    # Load into a fresh store
    fresh_store = SessionStore(ttl_seconds=3600, max_turns=50)
    await fresh_store.load_from_graph(session=fake_session)

    restored = await fresh_store.get_turns("player1", "npc1")
    assert restored == ["hello", "world"], f"Expected restored turns, got {restored}"


@pytest.mark.asyncio
async def test_save_swallows_graph_error() -> None:
    """A graph error during save_to_graph must be logged and swallowed — must NOT raise."""
    store = SessionStore(ttl_seconds=3600, max_turns=50)
    await store.append_turns("player1", "npc2", ["turn1"])

    broken_session = MagicMock()
    broken_session.run = AsyncMock(side_effect=RuntimeError("neo4j down"))

    # Must not raise
    await store.save_to_graph(session=broken_session, max_persisted_turns=20)


@pytest.mark.asyncio
async def test_load_empty_graph_returns_empty() -> None:
    """load_from_graph when Neo4j returns no rows must leave the store empty."""
    fake_session = _FakeSession()
    fake_session.set_read_rows([])

    fresh_store = SessionStore(ttl_seconds=3600, max_turns=50)
    await fresh_store.load_from_graph(session=fake_session)

    active = await fresh_store.get_active_npc_ids(min_turns=1)
    assert active == [], f"Expected empty active list, got {active}"


@pytest.mark.asyncio
async def test_save_caps_at_max_persisted_turns() -> None:
    """save_to_graph must only persist the last max_persisted_turns turns."""
    store = SessionStore(ttl_seconds=3600, max_turns=500)
    many_turns = [f"turn-{i}" for i in range(100)]
    await store.append_turns("player1", "npc3", many_turns)

    fake_session = _FakeSession()
    await store.save_to_graph(session=fake_session, max_persisted_turns=10)

    assert fake_session.written_calls, "Expected write call"
    call_params = fake_session.written_calls[0]
    turns_json_val = call_params.get("turns_json")
    assert turns_json_val is not None, "Expected turns_json param"
    written_turns = json.loads(str(turns_json_val))
    assert len(written_turns) <= 10, (
        f"Expected at most 10 persisted turns, got {len(written_turns)}"
    )
    assert written_turns == many_turns[-10:], "Expected last 10 turns to be persisted"
