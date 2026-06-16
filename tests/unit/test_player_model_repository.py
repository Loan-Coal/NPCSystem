"""Unit tests for Neo4jPlayerModelRepository (DEC-122 / SEV-24 Wave 3).

Covers the PlayerModelGraphPort adapter against a fake GraphDB (session-per-call seam):
upsert_player_model opens one session and delegates to player_model_writer.upsert_player_model.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.player_model_repository import Neo4jPlayerModelRepository

_PLAYER_MODEL_MOD = "npc_engine.graph.repositories.player_model_repository"


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
async def test_upsert_player_model_delegates_to_writer():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPlayerModelRepository(db)  # type: ignore[arg-type]

    with patch(f"{_PLAYER_MODEL_MOD}.upsert_player_model", new=AsyncMock()) as mock_fn:
        await repo.upsert_player_model(
            npc_id="npc_a", player_id="player_1", perceived_trust=85,
            perceived_intent="friendly", tick=12,
        )

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(
        session=session, npc_id="npc_a", player_id="player_1",
        perceived_trust=85, perceived_intent="friendly", tick=12,
    )
