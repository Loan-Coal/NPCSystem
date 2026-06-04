"""
Unit tests for SEV-29 gossip N+1 query fix.

Verifies that for N gossip pairs the gossip handler issues at most 2 session.run
calls for the read+propagate phase (not N×3). The extra conditional calls for
log_gossip, create_rumor, and believe_rumor are excluded from the count by
patching those helpers directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_handler import GossipHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings():
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = 999  # never triggers rumor path
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = 999
    return s


def _make_weight_config():
    cfg = MagicMock()
    cfg.hostile_distortion_factor = 1.0
    return cfg


def _make_handler():
    return GossipHandler(
        settings=_make_settings(),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
    )


def _make_pairs(n: int) -> list:
    return [
        (
            {"id": f"sharer-{i}", "honesty": 50},
            {"id": f"receiver-{i}"},
            f"loc-{i}",
            {"best_standing": None},
        )
        for i in range(n)
    ]


def _make_batch_rows(n: int) -> list[dict]:
    """Return batch read rows matching the expected select_batch_event_trust output."""
    return [
        {
            "sharer_id": f"sharer-{i}",
            "receiver_id": f"receiver-{i}",
            "event_id": f"event-{i}",
            "summary": f"summary-{i}",
            "severity": 30,
            "is_canonical": False,
            "trust": 60,
        }
        for i in range(n)
    ]


def _make_async_iter(records: list[dict]):
    """Return an async iterator over the given records."""

    async def _gen():
        for r in records:
            yield r

    return _gen()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gossip_tick_at_most_2_session_run_calls_for_3_pairs():
    """For 3 pairs the handler must issue at most 2 session.run calls total.

    The old N+1 shape issued 2 reads (event + trust) + 1 write (propagate)
    per pair = N×3 = 9 calls.  After the batch fix it should be at most 2 calls
    regardless of N: one batched read query and one batched write query.
    """
    handler = _make_handler()
    session = AsyncMock()

    n_pairs = 3
    pairs = _make_pairs(n_pairs)
    batch_rows = _make_batch_rows(n_pairs)

    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter(batch_rows))
    read_result.consume = AsyncMock()

    write_result = AsyncMock()
    write_result.consume = AsyncMock()

    # session.run: 1st call = batch read, 2nd call = batch write
    session.run = AsyncMock(side_effect=[read_result, write_result])

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.log_gossip",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random,
    ):
        mock_random.random.return_value = 1.0  # skip secret propagation branch

        await handler.run_tick(session=session, tick_id=1)

    # Core assertion: at most 2 session.run calls (1 batch read + 1 batch write)
    assert session.run.call_count <= 2, (
        f"Expected at most 2 session.run calls for {n_pairs} pairs "
        f"but got {session.run.call_count}"
    )


@pytest.mark.asyncio
async def test_gossip_tick_result_counts_match_pairs():
    """run_tick must return propagated == number of pairs with valid events."""
    handler = _make_handler()
    session = AsyncMock()

    n_pairs = 4
    pairs = _make_pairs(n_pairs)
    batch_rows = _make_batch_rows(n_pairs)

    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter(batch_rows))
    read_result.consume = AsyncMock()

    write_result = AsyncMock()
    write_result.consume = AsyncMock()

    session.run = AsyncMock(side_effect=[read_result, write_result])

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.log_gossip",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random,
    ):
        mock_random.random.return_value = 1.0

        result = await handler.run_tick(session=session, tick_id=5)

    assert result["propagated"] == n_pairs
    assert result["pairs"] == n_pairs
    assert result["tick_id"] == 5


@pytest.mark.asyncio
async def test_gossip_tick_skips_pairs_with_no_event():
    """Pairs for which no event is returned must be skipped (propagated not incremented)."""
    handler = _make_handler()
    session = AsyncMock()

    # 3 pairs but batch read only returns rows for 2 of them
    pairs = _make_pairs(3)
    batch_rows = [
        {
            "sharer_id": "sharer-0",
            "receiver_id": "receiver-0",
            "event_id": "event-0",
            "summary": "summary-0",
            "severity": 30,
            "is_canonical": False,
            "trust": 60,
        },
        {
            "sharer_id": "sharer-2",
            "receiver_id": "receiver-2",
            "event_id": "event-2",
            "summary": "summary-2",
            "severity": 50,
            "is_canonical": True,
            "trust": 80,
        },
    ]

    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter(batch_rows))
    read_result.consume = AsyncMock()

    write_result = AsyncMock()
    write_result.consume = AsyncMock()

    session.run = AsyncMock(side_effect=[read_result, write_result])

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.log_gossip",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random,
    ):
        mock_random.random.return_value = 1.0

        result = await handler.run_tick(session=session, tick_id=1)

    assert result["propagated"] == 2
    assert result["pairs"] == 3
