"""
test_event_feed_queries.py - Unit tests for graph.event_feed_queries.get_recent_event_feed.

Does NOT: run against a live Neo4j instance.

Dependencies: pytest, unittest stubs for AsyncSession.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

pytest.importorskip("neo4j")

from npc_engine.graph.event.event_feed_queries import get_recent_event_feed


@dataclass
class _Row:
    """Simulates a neo4j result row with dict-style access."""

    _data: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        return self._data[key]


@dataclass
class _ResultStub:
    rows: list[dict[str, Any]]

    async def data(self) -> list[dict[str, Any]]:
        return list(self.rows)

    async def consume(self) -> None:
        pass


@dataclass
class _SessionStub:
    result: _ResultStub
    last_params: dict[str, Any] = field(default_factory=dict)

    async def run(self, query: str, **params: Any) -> _ResultStub:
        self.last_params = dict(params)
        return self.result


def _make_session(rows: list[dict[str, Any]]) -> _SessionStub:
    return _SessionStub(result=_ResultStub(rows=rows))


_SAMPLE_ROW: dict[str, Any] = {
    "event_id": "evt_001",
    "event_type": "northern_war_begins",
    "label": "War begins",
    "severity": 9,
    "tick_id": 3,
    "location_id": "guard_barracks",
    "src_character_id": "captain_sorn",
}


class TestGetRecentEventFeedHappyPath:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self) -> None:
        """Returns a list with one dict when the session returns one row."""
        session = _make_session([_SAMPLE_ROW])
        result = await get_recent_event_feed(session)  # type: ignore[arg-type]
        assert len(result) == 1
        assert result[0]["event_id"] == "evt_001"
        assert result[0]["event_type"] == "northern_war_begins"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_events(self) -> None:
        """Returns [] when Neo4j returns no rows."""
        session = _make_session([])
        result = await get_recent_event_feed(session)  # type: ignore[arg-type]
        assert result == []

    @pytest.mark.asyncio
    async def test_passes_limit_to_session(self) -> None:
        """The limit parameter is forwarded to the Cypher query."""
        session = _make_session([])
        await get_recent_event_feed(session, limit=7)  # type: ignore[arg-type]
        assert session.last_params.get("limit") == 7

    @pytest.mark.asyncio
    async def test_default_limit_is_20(self) -> None:
        """Default limit is 20."""
        session = _make_session([])
        await get_recent_event_feed(session)  # type: ignore[arg-type]
        assert session.last_params.get("limit") == 20

    @pytest.mark.asyncio
    async def test_all_expected_keys_present(self) -> None:
        """Each returned dict contains the required keys."""
        session = _make_session([_SAMPLE_ROW])
        result = await get_recent_event_feed(session)  # type: ignore[arg-type]
        row = result[0]
        for key in ("event_id", "event_type", "label", "severity", "tick_id",
                    "location_id", "src_character_id"):
            assert key in row, f"missing key: {key}"


class TestGetRecentEventFeedLimitClamping:
    @pytest.mark.asyncio
    async def test_limit_clamped_to_minimum_1(self) -> None:
        """limit=0 is clamped to 1."""
        session = _make_session([])
        await get_recent_event_feed(session, limit=0)  # type: ignore[arg-type]
        assert session.last_params["limit"] == 1

    @pytest.mark.asyncio
    async def test_limit_clamped_to_maximum_100(self) -> None:
        """limit=999 is clamped to 100."""
        session = _make_session([])
        await get_recent_event_feed(session, limit=999)  # type: ignore[arg-type]
        assert session.last_params["limit"] == 100

    @pytest.mark.asyncio
    async def test_limit_at_boundary_100_not_clamped(self) -> None:
        """limit=100 passes through unchanged."""
        session = _make_session([])
        await get_recent_event_feed(session, limit=100)  # type: ignore[arg-type]
        assert session.last_params["limit"] == 100
