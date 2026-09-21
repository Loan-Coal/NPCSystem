"""Unit tests for the shared read repository adapters (DEC-122 / SEV-24 Wave 2).

Covers Neo4jPlayerLocationReadRepository and Neo4jCharacterReadRepository
against a fake GraphDB (session-per-call seam).
Neo4jRelationReadRepository tests removed: get_relation_scalars and
get_relation_phase_row are covered by integration tests (T11.2).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.repositories.character_read_repository import (
    Neo4jCharacterReadRepository,
)
from npc_engine.graph.repositories.player_location_read_repository import (
    Neo4jPlayerLocationReadRepository,
)

_CHARACTER_MOD = "npc_engine.graph.repositories.character_read_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


# --------------------------------------------------------------------------- #
# Neo4jPlayerLocationReadRepository
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_collocated_pairs_delegates_to_reader():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPlayerLocationReadRepository(db)  # type: ignore[arg-type]
    pairs = [("npc_1", "player_1")]
    repo._reader = MagicMock()
    repo._reader.get_collocated_pairs = AsyncMock(return_value=pairs)

    result = await repo.get_collocated_pairs()

    assert result == pairs
    assert db.connect_calls == 1
    repo._reader.get_collocated_pairs.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_get_player_idle_ticks_delegates_to_reader():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPlayerLocationReadRepository(db)  # type: ignore[arg-type]
    repo._reader = MagicMock()
    repo._reader.get_player_idle_ticks = AsyncMock(return_value=4)

    result = await repo.get_player_idle_ticks(
        npc_id="npc_1", player_id="player_1", tick_id=10
    )

    assert result == 4
    assert db.connect_calls == 1
    repo._reader.get_player_idle_ticks.assert_awaited_once_with(
        session, npc_id="npc_1", player_id="player_1", tick_id=10
    )


# --------------------------------------------------------------------------- #
# Neo4jCharacterReadRepository
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_npc_ids_delegates_to_query():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jCharacterReadRepository(db)  # type: ignore[arg-type]
    ids = ["npc_1", "npc_2"]

    with patch(
        f"{_CHARACTER_MOD}.get_npc_ids_query", new=AsyncMock(return_value=ids)
    ) as mock_fn:
        result = await repo.get_npc_ids()

    assert result == ids
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session)
