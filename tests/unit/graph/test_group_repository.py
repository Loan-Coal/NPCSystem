"""Unit tests for Neo4jGroupRepository (DEC-122 / SEV-24 graph repository seam).

Verifies the adapter connects, opens a session per call, and delegates to the
group graph queries/service — no real Neo4j involved.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.group_repository import Neo4jGroupRepository

_MOD = "npc_engine.graph.repositories.group_repository"


class _FakeGraphDB:
    """Minimal GraphDB stand-in recording connect() and yielding a fixed session."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_get_high_affection_pairs_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jGroupRepository(db)  # type: ignore[arg-type]
    rows = [{"char_a_id": "a", "char_b_id": "b"}]

    with patch(f"{_MOD}.get_high_affection_pairs", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_high_affection_pairs(threshold=70)

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, threshold=70)


@pytest.mark.asyncio
async def test_create_group_delegates_and_returns_id():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jGroupRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.create_group", new=AsyncMock(return_value="g-1")) as mock_fn:
        group_id = await repo.create_group(
            name="Clique", kind="clique", cohesion=10, is_secret=False, formed_at_tick=5
        )

    assert group_id == "g-1"
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(
        session, name="Clique", kind="clique", cohesion=10, is_secret=False, formed_at_tick=5
    )


@pytest.mark.asyncio
async def test_dissolve_group_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jGroupRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.dissolve_group", new=AsyncMock()) as mock_fn:
        await repo.dissolve_group(group_id="g-1", tick=9)

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, group_id="g-1", tick=9)
