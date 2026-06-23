"""
test_faction_writer.py - Unit tests for faction mutation graph functions.

Does NOT: use a real Neo4j connection.

Dependencies injected: fake async transaction stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from npc_engine.graph.faction.faction_writer import (
    CYPHER_ADD_MEMBER,
    CYPHER_REMOVE_MEMBER,
    CYPHER_SET_CONTROLS,
    CYPHER_REMOVE_CONTROLS,
    CYPHER_SET_STANDING,
    CYPHER_UPSERT_FACTION,
    add_member,
    remove_member,
    remove_controls,
    set_controls,
    set_standing,
    upsert_faction,
)
from npc_engine.utils.errors import FactionMembershipError, FactionNotFoundError


# ---------------------------------------------------------------------------
# Fake async stubs
# ---------------------------------------------------------------------------


@dataclass
class _FakeResult:
    _record: dict | None

    async def single(self) -> dict | None:
        return self._record

    async def consume(self) -> _FakeSummary:
        return _FakeSummary(deleted=self._record is not None)


@dataclass
class _FakeSummary:
    deleted: bool

    @property
    def counters(self) -> _FakeCounters:
        return _FakeCounters(nodes_deleted=1 if self.deleted else 0, relationships_deleted=1 if self.deleted else 0)


@dataclass
class _FakeCounters:
    nodes_deleted: int
    relationships_deleted: int


class _FakeTx:
    def __init__(self, handler: Any = None) -> None:
        self._handler = handler or (lambda q, p: {"found": True})
        self.calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.calls.append((query, params))
        record = self._handler(query, params)
        return _FakeResult(_record=record)


# ---------------------------------------------------------------------------
# upsert_faction
# ---------------------------------------------------------------------------


@dataclass
class _FactionModel:
    """Minimal faction fixture that mimics the Pydantic model interface."""

    id: str
    name: str
    archetype: str
    is_active: bool
    created_at: str
    last_graph_updated_at: str
    description: str | None = None

    def model_dump(self, *, mode: str = "python") -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "archetype": self.archetype,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_graph_updated_at": self.last_graph_updated_at,
        }


@pytest.mark.asyncio
async def test_upsert_faction_runs_merge_with_id_and_properties() -> None:
    tx = _FakeTx()
    faction = _FactionModel(
        id="faction-1",
        name="The Iron Hand",
        archetype="military",
        is_active=True,
        created_at="2026-01-01T00:00:00",
        last_graph_updated_at="2026-01-01T00:00:00",
    )

    await upsert_faction(tx, faction)  # type: ignore[arg-type]

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_UPSERT_FACTION
    assert params["id"] == "faction-1"
    assert "name" in params["properties"]


# ---------------------------------------------------------------------------
# add_member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_member_runs_merge_with_role_and_status() -> None:
    tx = _FakeTx()

    await add_member(tx, character_id="char-1", faction_id="faction-1", role="member", status="active")

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_ADD_MEMBER
    assert params["character_id"] == "char-1"
    assert params["faction_id"] == "faction-1"
    assert params["role"] == "member"
    assert params["status"] == "active"


# ---------------------------------------------------------------------------
# remove_member
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_member_succeeds_when_edge_exists() -> None:
    tx = _FakeTx(handler=lambda q, p: {"deleted": True})

    await remove_member(tx, character_id="char-1", faction_id="faction-1")

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_REMOVE_MEMBER
    assert params["character_id"] == "char-1"
    assert params["faction_id"] == "faction-1"


@pytest.mark.asyncio
async def test_remove_member_raises_when_edge_missing() -> None:
    tx = _FakeTx(handler=lambda q, p: None)

    with pytest.raises(FactionMembershipError) as exc_info:
        await remove_member(tx, character_id="char-99", faction_id="faction-1")

    assert exc_info.value.character_id == "char-99"
    assert exc_info.value.faction_id == "faction-1"


# ---------------------------------------------------------------------------
# set_standing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_standing_runs_merge_with_correct_params() -> None:
    tx = _FakeTx()

    await set_standing(tx, src_id="faction-a", dst_id="faction-b", standing=75)

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_SET_STANDING
    assert params["src_id"] == "faction-a"
    assert params["dst_id"] == "faction-b"
    assert params["standing"] == 75


@pytest.mark.asyncio
async def test_set_standing_raises_on_missing_src_faction() -> None:
    tx = _FakeTx(handler=lambda q, p: None)

    with pytest.raises(FactionNotFoundError):
        await set_standing(tx, src_id="ghost", dst_id="faction-b", standing=0)


# ---------------------------------------------------------------------------
# set_controls / remove_controls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_controls_runs_merge_with_correct_params() -> None:
    tx = _FakeTx()

    await set_controls(tx, faction_id="faction-1", location_id="loc-1")

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_SET_CONTROLS
    assert params["faction_id"] == "faction-1"
    assert params["location_id"] == "loc-1"


@pytest.mark.asyncio
async def test_remove_controls_succeeds_when_edge_exists() -> None:
    tx = _FakeTx(handler=lambda q, p: {"deleted": True})

    await remove_controls(tx, faction_id="faction-1", location_id="loc-1")

    assert len(tx.calls) == 1
    query, params = tx.calls[0]
    assert query == CYPHER_REMOVE_CONTROLS


@pytest.mark.asyncio
async def test_remove_controls_raises_when_edge_missing() -> None:
    tx = _FakeTx(handler=lambda q, p: None)

    with pytest.raises(FactionNotFoundError):
        await remove_controls(tx, faction_id="faction-ghost", location_id="loc-1")
