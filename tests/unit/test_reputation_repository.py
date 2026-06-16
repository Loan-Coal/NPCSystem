"""Unit tests for Neo4jReputationRepository (DEC-122 / SEV-24 Wave 3).

Covers the ReputationGraphPort adapter against a fake GraphDB (session-per-call seam):
apply_trust_nudge opens one session and delegates to graph.reputation_nudge.apply_trust_nudge.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.reputation_repository import Neo4jReputationRepository

_REPUTATION_MOD = "npc_engine.graph.repositories.reputation_repository"


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
async def test_apply_trust_nudge_delegates_to_writer():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jReputationRepository(db)  # type: ignore[arg-type]

    with patch(f"{_REPUTATION_MOD}.apply_trust_nudge", new=AsyncMock()) as mock_fn:
        await repo.apply_trust_nudge(
            src_id="B", dst_id="player", delta_trust=2, delta_affection=0
        )

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(
        session, src_id="B", dst_id="player", delta_trust=2, delta_affection=0
    )
