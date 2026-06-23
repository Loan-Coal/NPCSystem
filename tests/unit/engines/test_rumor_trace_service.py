"""
Unit tests for rumor_trace_service (S10.3).

Covers trace_rumor_chain (happy path, empty result) and correct_rumor_at_npc
(edge found, edge not found).  All Neo4j I/O is replaced with AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.gossip.rumor_trace_service import (
    correct_rumor_at_npc,
    trace_rumor_chain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeRecord:
    """Minimal Neo4j-record lookalike that supports dict(record)."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def __iter__(self):
        return iter(self._data.items())

    def data(self) -> dict:
        """Return raw data dict."""
        return dict(self._data)


class _AsyncIterResult:
    """Fake Neo4j result that supports 'async for record in result' and consume()."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __aiter__(self):
        return self._async_gen()

    async def _async_gen(self):
        for row in self._rows:
            yield _FakeRecord(row)

    async def consume(self):
        pass


def _session_with_rows(rows: list[dict]) -> AsyncMock:
    """Return AsyncMock session whose run() returns an async-iterable result."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=_AsyncIterResult(rows))
    return session


def _session_with_single(record_data: dict | None) -> AsyncMock:
    """Return AsyncMock session whose run().single() returns one record or None."""
    session = AsyncMock()
    result = AsyncMock()
    result.consume = AsyncMock()

    if record_data is not None:
        rec = MagicMock()
        rec.__getitem__ = lambda self, k, _d=record_data: _d[k]
        result.single = AsyncMock(return_value=rec)
    else:
        result.single = AsyncMock(return_value=None)

    session.run = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# trace_rumor_chain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trace_rumor_chain_returns_ordered_rows():
    rows = [
        {
            "npc_id": "captain_sorn",
            "npc_name": "Captain Sorn",
            "knowledge_state": "rumor",
            "learned_at_tick": 1,
            "distorted_summary": None,
        },
        {
            "npc_id": "mira_innkeeper",
            "npc_name": "Mira",
            "knowledge_state": "rumor",
            "learned_at_tick": 2,
            "distorted_summary": "A spy was spotted near the castle.",
        },
    ]
    session = _session_with_rows(rows)
    chain = await trace_rumor_chain(session, "rumor_plant_captain_sorn_1")
    assert len(chain) == 2
    assert chain[0]["npc_id"] == "captain_sorn"
    assert chain[1]["npc_id"] == "mira_innkeeper"
    assert chain[1]["distorted_summary"] == "A spy was spotted near the castle."


@pytest.mark.asyncio
async def test_trace_rumor_chain_empty_when_no_holders():
    session = _session_with_rows([])
    chain = await trace_rumor_chain(session, "nonexistent_event")
    assert chain == []


@pytest.mark.asyncio
async def test_trace_rumor_chain_passes_event_id_to_query():
    session = _session_with_rows([])
    await trace_rumor_chain(session, "my_event_id")
    session.run.assert_called_once()
    _, kwargs = session.run.call_args
    assert kwargs["event_id"] == "my_event_id"


# ---------------------------------------------------------------------------
# correct_rumor_at_npc
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correct_rumor_returns_true_when_edge_updated():
    session = _session_with_single({"updated": 1})
    result = await correct_rumor_at_npc(session, "mira_innkeeper", "rumor_plant_captain_sorn_1")
    assert result is True


@pytest.mark.asyncio
async def test_correct_rumor_returns_false_when_count_zero():
    session = _session_with_single({"updated": 0})
    result = await correct_rumor_at_npc(session, "mira_innkeeper", "unknown_event")
    assert result is False


@pytest.mark.asyncio
async def test_correct_rumor_returns_false_when_no_record():
    session = _session_with_single(None)
    result = await correct_rumor_at_npc(session, "mira_innkeeper", "unknown_event")
    assert result is False


@pytest.mark.asyncio
async def test_correct_rumor_passes_corrected_state_to_query():
    session = _session_with_single({"updated": 1})
    await correct_rumor_at_npc(session, "old_henryk", "rumor_plant_lira_fence_5")
    _, kwargs = session.run.call_args
    assert kwargs["corrected_state"] == "corrected"
    assert kwargs["npc_id"] == "old_henryk"
    assert kwargs["event_id"] == "rumor_plant_lira_fence_5"
