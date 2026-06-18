"""Unit tests for Neo4jRelationPhaseWriteRepository (DEC-122 / SEV-24 relationship).

Covers the RelationPhaseWritePort adapter against a fake GraphDB (session-per-call seam):
the method opens one session and delegates to relation_phase_writer.write_relationship_phase.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.relation_phase_write_repository import (
    Neo4jRelationPhaseWriteRepository,
)

_MOD = "npc_engine.graph.repositories.relation_phase_write_repository"


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
async def test_write_relationship_phase_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jRelationPhaseWriteRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.write_relationship_phase", new=AsyncMock()) as fn:
        await repo.write_relationship_phase(
            src_id="npc_a", dst_id="player_1", phase="CLOSE", tick=42
        )

    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session, "npc_a", "player_1", "CLOSE", 42)
