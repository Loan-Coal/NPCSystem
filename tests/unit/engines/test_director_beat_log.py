"""
test_director_beat_log.py - Unit tests for the in-memory DirectorBeatLog (F2.4).

Verifies recording, newest-first recent() reads, the limit argument, and bounded
retention (oldest beats drop once the cap is exceeded).

Dependencies injected: none (pure in-memory store).
"""

from __future__ import annotations

import pytest

from npc_engine.engines.director.director_beat_log import (
    MAX_RECENT_BEATS,
    DirectorBeatLog,
    DirectorBeatRecord,
)


def _beat(tick: int) -> DirectorBeatRecord:
    return DirectorBeatRecord(
        beat_kind="re_engage_idle", reason=f"tick {tick}",
        npc_id="npc_a", player_id="player_1", tick=tick,
    )


@pytest.mark.asyncio
async def test_records_and_reads_newest_first() -> None:
    """recent() returns the most recently recorded beats first."""
    log = DirectorBeatLog()
    await log.record(_beat(1))
    await log.record(_beat(2))

    recent = log.recent(limit=10)

    assert [b.tick for b in recent] == [2, 1]


@pytest.mark.asyncio
async def test_recent_honours_limit() -> None:
    """recent(limit) returns at most `limit` newest beats."""
    log = DirectorBeatLog()
    for tick in range(5):
        await log.record(_beat(tick))

    recent = log.recent(limit=2)

    assert [b.tick for b in recent] == [4, 3]


@pytest.mark.asyncio
async def test_bounded_retention_drops_oldest() -> None:
    """The log retains at most MAX_RECENT_BEATS, dropping the oldest."""
    log = DirectorBeatLog()
    total = MAX_RECENT_BEATS + 5
    for tick in range(total):
        await log.record(_beat(tick))

    recent = log.recent(limit=total)

    assert len(recent) == MAX_RECENT_BEATS
    assert recent[0].tick == total - 1  # newest retained
    assert recent[-1].tick == total - MAX_RECENT_BEATS  # oldest retained
