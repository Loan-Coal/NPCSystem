"""
test_incremental_corpus_upsert.py - Unit tests for DEC-210's incremental corpus upsert.

The instrument wants a corpus that cannot move; the product wants one that tracks the
graph. These pin both halves: the flag actually gates the write, and the OFF state is
verifiable by the ABSENCE of a log line rather than by reading .env — DEC-206 is the
precedent, where a flag was "off" and produced 30 nodes anyway.

Does NOT: connect to Neo4j or run a sentence encoder.

Dependencies injected: fake refresher, fake index, explicit log handler.
"""

from __future__ import annotations

import logging

import pytest

from npc_engine.engines.embedding_refresh import (
    INCREMENTAL_UPSERT_LOG_EVENT,
    refresh_embedding_safely,
)

LOGGER = logging.getLogger("test_incremental_corpus_upsert")


class FakeIndex:
    def __init__(self) -> None:
        self.invalidated: list[str] = []

    async def invalidate(self, item_id: str) -> None:
        self.invalidated.append(item_id)


class FakeRefresher:
    def __init__(self, *, refreshed: bool = True, boom: bool = False) -> None:
        self.calls: list[str] = []
        self._refreshed = refreshed
        self._boom = boom

    async def refresh(self, node_id: str) -> bool:
        self.calls.append(node_id)
        if self._boom:
            raise RuntimeError("neo4j went away mid-tick")
        return self._refreshed


def _capture(logger: logging.Logger) -> tuple[list[logging.LogRecord], logging.Handler]:
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return records, handler


@pytest.mark.asyncio
async def test_the_upsert_runs_and_announces_itself_when_the_flag_is_on() -> None:
    index, refresher = FakeIndex(), FakeRefresher()
    records, handler = _capture(LOGGER)
    try:
        await refresh_embedding_safely(
            embedding_index=index, refresher=refresher, item_id="evt_1",
            enabled=True, logger=LOGGER, entity_label="event",
        )
    finally:
        LOGGER.removeHandler(handler)

    assert index.invalidated == ["evt_1"]
    assert refresher.calls == ["evt_1"]
    assert any(INCREMENTAL_UPSERT_LOG_EVENT in record.getMessage() for record in records)


@pytest.mark.asyncio
async def test_the_upsert_is_silent_and_absent_when_the_flag_is_off() -> None:
    """P10 gate 6 checks the ABSENCE of this line during a probe turn.

    A flag is worth nothing unverified: in DEC-206 the tick autopilot was 'off' and
    produced 24 FactionStandingEvent, 5 Quest and 1 Chapter node anyway, and only a
    line-by-line fixture diff caught it.
    """
    index, refresher = FakeIndex(), FakeRefresher()
    records, handler = _capture(LOGGER)
    try:
        await refresh_embedding_safely(
            embedding_index=index, refresher=refresher, item_id="evt_1",
            enabled=False, logger=LOGGER, entity_label="event",
        )
    finally:
        LOGGER.removeHandler(handler)

    assert index.invalidated == ["evt_1"], "invalidation is unconditional; only the insert is flagged"
    assert refresher.calls == []
    assert not [r for r in records if INCREMENTAL_UPSERT_LOG_EVENT in r.getMessage()]


@pytest.mark.asyncio
async def test_a_refresh_failure_never_breaks_the_handler() -> None:
    """Corpus freshness is best-effort; an event must still be emitted."""
    index, refresher = FakeIndex(), FakeRefresher(boom=True)
    records, handler = _capture(LOGGER)
    try:
        await refresh_embedding_safely(
            embedding_index=index, refresher=refresher, item_id="evt_1",
            enabled=True, logger=LOGGER, entity_label="event",
        )
    finally:
        LOGGER.removeHandler(handler)

    assert any(record.levelno >= logging.WARNING for record in records)


@pytest.mark.asyncio
async def test_no_refresher_wired_degrades_to_invalidate_only() -> None:
    index = FakeIndex()
    await refresh_embedding_safely(
        embedding_index=index, refresher=None, item_id="evt_1",
        enabled=True, logger=LOGGER, entity_label="event",
    )
    assert index.invalidated == ["evt_1"]
