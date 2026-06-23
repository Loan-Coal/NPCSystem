"""
Regression tests for SEV-04: story_pacing domain Cypher migrated to graph layer.

Verifies that:
1. graph.story_pacing_queries exports the two reader functions.
2. Functions return typed results via a mock session.
3. Engine delegates to graph functions (no direct session.run).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.narrative.story_pacing_queries import (
    get_active_high_severity_quests,
    get_recent_major_events,
)
from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.world.world_state import WorldState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RULES = PacingRules(
    high_severity_quest_threshold=70,
    suppression_event_severity_cap=30,
    suppression_quest_rate=0.5,
    cooldown_ticks=10,
    major_event_severity_floor=60,
)


@dataclass
class _AsyncIter:
    _items: list[Any]
    _idx: int = field(default=0, init=False)

    def __aiter__(self) -> "_AsyncIter":
        return self

    async def __anext__(self) -> Any:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _FakeRecord(dict):
    """Dict subclass that also supports attribute-style access."""


def _make_result(rows: list[dict]) -> Any:
    """Return an async-iterable fake query result for the given rows."""
    records = [_FakeRecord(row) for row in rows]
    result = AsyncMock()
    result.__aiter__ = lambda self: _AsyncIter(records)
    return result


# ---------------------------------------------------------------------------
# graph.story_pacing_queries — unit tests (mock session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_high_severity_quests_returns_list() -> None:
    """get_active_high_severity_quests returns a list of dicts with quest_id/severity."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_make_result([{"quest_id": "q1", "severity": 80}]))

    result = await get_active_high_severity_quests(session=session, threshold=70)

    assert isinstance(result, list)
    assert result[0]["quest_id"] == "q1"
    assert result[0]["severity"] == 80


@pytest.mark.asyncio
async def test_get_recent_major_events_returns_list() -> None:
    """get_recent_major_events returns a list of dicts with event_id/severity/tick_id."""
    session = AsyncMock()
    session.run = AsyncMock(
        return_value=_make_result([{"event_id": "e1", "severity": 75, "tick_id": 5}])
    )

    result = await get_recent_major_events(session=session, min_tick_id=0, floor=60)

    assert isinstance(result, list)
    assert result[0]["event_id"] == "e1"
    assert result[0]["severity"] == 75
    assert result[0]["tick_id"] == 5


# ---------------------------------------------------------------------------
# Engine delegates to graph functions (no direct session.run)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_delegates_to_graph_ports() -> None:
    """StoryPacingEngine.run_tick delegates to its injected graph ports (no session).

    Post-SEV-24 the engine imports no graph symbol at all — it depends on the injected
    StoryPacingGraphPort + WorldStateGraphPort (whose Neo4j adapters live in graph/).
    """
    story_repo = AsyncMock()
    story_repo.get_active_high_severity_quests = AsyncMock(
        return_value=[{"quest_id": "q1", "severity": 80}]
    )
    story_repo.get_recent_major_events = AsyncMock(return_value=[])
    ws_repo = AsyncMock()
    ws_repo.get_world_state = AsyncMock(return_value=WorldState())
    ws_repo.upsert_world_state = AsyncMock(side_effect=lambda *, world_state: world_state)

    engine = StoryPacingEngine(
        rules=_RULES, story_pacing_repo=story_repo, world_state_repo=ws_repo
    )

    result = await engine.run_tick(tick_id=5)

    story_repo.get_active_high_severity_quests.assert_awaited_once()
    story_repo.get_recent_major_events.assert_awaited_once()
    ws_repo.upsert_world_state.assert_awaited_once()
    assert result["suppressed"] is True
