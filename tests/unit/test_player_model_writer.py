"""
test_player_model_writer.py - Unit tests for PlayerModelGraphWriter.

Does NOT: execute real Neo4j I/O.

Dependencies injected: None (stub AsyncSession/Transaction).
"""

from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FakeResult:
    """Stub Neo4j result with consume support."""

    async def consume(self) -> None:
        pass


class _FakeTx:
    """Stub Neo4j AsyncTransaction that records the last run call."""

    def __init__(self) -> None:
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}
        self.committed: bool = False

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.last_query = query
        self.last_params = params
        return _FakeResult()

    async def commit(self) -> None:
        self.committed = True

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class _FakeSession:
    """Stub Neo4j AsyncSession returning a _FakeTx."""

    def __init__(self) -> None:
        self.tx = _FakeTx()

    async def begin_transaction(self) -> _FakeTx:
        return self.tx

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.tx.last_query = query
        self.tx.last_params = params
        return _FakeResult()


# ---------------------------------------------------------------------------
# upsert_player_model tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_targets_player_model_node() -> None:
    """upsert_player_model Cypher targets the player_model node label."""
    from npc_engine.graph.player_model_writer import upsert_player_model

    session = _FakeSession()
    await upsert_player_model(
        session=session,
        npc_id="npc_a",
        player_id="player_1",
        perceived_trust=75,
        perceived_intent="friendly",
        tick=10,
    )

    assert "player_model" in session.tx.last_query.lower()


@pytest.mark.asyncio
async def test_upsert_targets_has_player_model_edge() -> None:
    """upsert_player_model Cypher creates/merges the HAS_PLAYER_MODEL edge."""
    from npc_engine.graph.player_model_writer import upsert_player_model

    session = _FakeSession()
    await upsert_player_model(
        session=session,
        npc_id="npc_b",
        player_id="player_1",
        perceived_trust=30,
        perceived_intent="neutral",
        tick=5,
    )

    assert "HAS_PLAYER_MODEL" in session.tx.last_query


@pytest.mark.asyncio
async def test_upsert_passes_correct_params() -> None:
    """upsert_player_model passes npc_id, player_id, perceived_trust, perceived_intent."""
    from npc_engine.graph.player_model_writer import upsert_player_model

    session = _FakeSession()
    await upsert_player_model(
        session=session,
        npc_id="npc_c",
        player_id="player_2",
        perceived_trust=50,
        perceived_intent="hostile",
        tick=7,
    )

    params = session.tx.last_params
    assert params["npc_id"] == "npc_c"
    assert params["player_id"] == "player_2"
    assert params["perceived_trust"] == 50
    assert params["perceived_intent"] == "hostile"


# ---------------------------------------------------------------------------
# get_player_model tests
# ---------------------------------------------------------------------------


class _FakeReadSession:
    """Stub AsyncSession for read path returning a single record."""

    def __init__(self, record: dict[str, Any] | None) -> None:
        self._record = record
        self.last_query: str = ""
        self.last_params: dict[str, Any] = {}

    async def run(self, query: str, **params: Any) -> "_FakeReadResult":
        self.last_query = query
        self.last_params = params
        return _FakeReadResult(self._record)


class _FakeReadResult:
    """Stub result for single-record reads."""

    def __init__(self, record: dict[str, Any] | None) -> None:
        self._record = record

    async def single(self) -> "_FakeRecord | None":
        if self._record is None:
            return None
        return _FakeRecord(self._record)


class _FakeRecord:
    """Stub Neo4j record mapping."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def data(self) -> dict[str, Any]:
        return self._data


@pytest.mark.asyncio
async def test_get_player_model_returns_none_when_missing() -> None:
    """get_player_model returns None when no node exists for the npc/player pair."""
    from npc_engine.graph.player_model_writer import get_player_model

    session = _FakeReadSession(record=None)
    result = await get_player_model(session=session, npc_id="npc_x", player_id="player_z")

    assert result is None


@pytest.mark.asyncio
async def test_get_player_model_returns_model_when_present() -> None:
    """get_player_model returns a PlayerModelRecord when node is found."""
    from npc_engine.graph.player_model_writer import PlayerModelRecord, get_player_model

    session = _FakeReadSession(
        record={
            "pm.id": "npc_a__player_1",
            "pm.npc_id": "npc_a",
            "pm.player_id": "player_1",
            "pm.perceived_trust": 60,
            "pm.perceived_intent": "neutral",
            "pm.last_updated_at": "10",
        }
    )
    result = await get_player_model(session=session, npc_id="npc_a", player_id="player_1")

    assert result is not None
    assert isinstance(result, PlayerModelRecord)
    assert result.npc_id == "npc_a"
    assert result.perceived_trust == 60
