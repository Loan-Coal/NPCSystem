"""Unit tests for Neo4jProactiveMemoryReadRepository (DEC-122 / SEV-24 proactive_dialogue).

Covers the ProactiveMemoryReadPort adapter against a fake GraphDB (session-per-call seam):
the method opens one session and delegates to ProactiveMemoryReader.get_unshared_memories.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.proactive_memory_read_repository import (
    Neo4jProactiveMemoryReadRepository,
)

_MOD = "npc_engine.graph.repositories.proactive_memory_read_repository"


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
async def test_get_unshared_memories_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jProactiveMemoryReadRepository(db)  # type: ignore[arg-type]
    rows = [{"memory_id": "m1", "content": "x", "vividness": 80, "shared": False}]

    with patch(
        f"{_MOD}.ProactiveMemoryReader.get_unshared_memories",
        new=AsyncMock(return_value=rows),
    ) as fn:
        result = await repo.get_unshared_memories(npc_id="mira", k=5)

    assert result == rows
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session, npc_id="mira", k=5)
