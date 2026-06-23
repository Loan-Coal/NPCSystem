"""Unit tests for Neo4jKnowledgeRepository (DEC-122 / SEV-24 Wave 2 knowledge slice).

Covers the session-per-call belief read/write adapter against a fake GraphDB.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.knowledge_repository import Neo4jKnowledgeRepository

_KNOWLEDGE_MOD = "npc_engine.graph.repositories.knowledge_repository"


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
async def test_find_conflicting_belief_delegates_to_query() -> None:
    """Adapter must connect, open a session, and delegate to find_conflicting_belief."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jKnowledgeRepository(db)  # type: ignore[arg-type]
    existing = {"id": "b1", "content": "x"}

    with patch(
        f"{_KNOWLEDGE_MOD}.find_conflicting_belief",
        new=AsyncMock(return_value=existing),
    ) as mock_fn:
        result = await repo.find_conflicting_belief(character_id="npc-1", content="x")

    assert result is existing
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, character_id="npc-1", content="x")


@pytest.mark.asyncio
async def test_write_belief_delegates_to_writer() -> None:
    """Adapter must connect, open a session, and delegate to write_belief, returning the id."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jKnowledgeRepository(db)  # type: ignore[arg-type]

    with patch(
        f"{_KNOWLEDGE_MOD}.write_belief", new=AsyncMock(return_value="belief-id")
    ) as mock_fn:
        result = await repo.write_belief(
            npc_id="npc-1",
            content="the gate is open",
            confidence=70,
            source_character_id="player-1",
            learned_at_tick=5,
            game_time_str="Year 1 Spring Day 1 Morning",
        )

    assert result == "belief-id"
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(
        session,
        npc_id="npc-1",
        content="the gate is open",
        confidence=70,
        source_character_id="player-1",
        learned_at_tick=5,
        game_time_str="Year 1 Spring Day 1 Morning",
        is_deception=False,
        deception_goal_id=None,
    )
