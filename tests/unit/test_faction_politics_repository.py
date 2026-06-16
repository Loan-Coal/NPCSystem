"""Unit tests for Neo4jFactionPoliticsRepository (SEV-24 faction_politics slice).

Covers the FactionPoliticsGraphPort adapter against a fake GraphDB (session-per-call
seam): each read opens one session and delegates to faction_politics_queries; the
commit runs set_standing via run_in_tx then appends the FactionStandingEvent.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.faction_politics_repository import (
    Neo4jFactionPoliticsRepository,
)

_MOD = "npc_engine.graph.repositories.faction_politics_repository"


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
async def test_get_recent_events_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jFactionPoliticsRepository(db)  # type: ignore[arg-type]
    rows = [{"event_id": "e", "event_type": "betrayal", "src_character_id": "c"}]
    with patch(f"{_MOD}.get_recent_events", new=AsyncMock(return_value=rows)) as fn:
        result = await repo.get_recent_events()
    assert result == rows
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session)


@pytest.mark.asyncio
async def test_get_character_factions_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jFactionPoliticsRepository(db)  # type: ignore[arg-type]
    with patch(f"{_MOD}.get_character_factions", new=AsyncMock(return_value=["f1"])) as fn:
        result = await repo.get_character_factions(character_id="char_a")
    assert result == ["f1"]
    fn.assert_awaited_once_with(db._session, character_id="char_a")


@pytest.mark.asyncio
async def test_get_all_standings_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jFactionPoliticsRepository(db)  # type: ignore[arg-type]
    standings = [{"src_id": "a", "dst_id": "b", "standing": 10}]
    with patch(f"{_MOD}.get_all_standings", new=AsyncMock(return_value=standings)) as fn:
        result = await repo.get_all_standings()
    assert result == standings
    fn.assert_awaited_once_with(db._session)


@pytest.mark.asyncio
async def test_commit_standing_change_writes_then_records() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jFactionPoliticsRepository(db)  # type: ignore[arg-type]
    with (
        patch(f"{_MOD}.run_in_tx", new=AsyncMock()) as run_tx,
        patch(f"{_MOD}.record_standing_change", new=AsyncMock()) as record,
    ):
        await repo.commit_standing_change(
            src_id="faction_a",
            dst_id="faction_b",
            new_standing=40,
            delta=-10,
            tick=7,
            cause_event_id="evt-1",
            cause_rule_id="betrayal",
        )
    assert db.connect_calls == 1
    run_tx.assert_awaited_once()
    assert run_tx.await_args.args[0] is db._session
    record.assert_awaited_once_with(
        db._session,
        src_faction_id="faction_a",
        dst_faction_id="faction_b",
        delta=-10,
        new_standing=40,
        tick=7,
        cause_event_id="evt-1",
        cause_rule_id="betrayal",
    )
