"""
Unit tests for SEV-29 gossip N+1 query fix.

Verifies that for N gossip pairs the gossip handler issues at most 1 batch read
and 1 batch write via the port (not N×3 per-pair calls).

Updated for SEV-24: uses GossipGraphPort mock instead of patching module-level
graph functions or counting session.run calls.
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


def _make_repo(batch_rows: list[dict]) -> MagicMock:
    repo = MagicMock()
    repo.select_batch_event_trust = AsyncMock(return_value=batch_rows)
    repo.write_batch_knowledge_propagation = AsyncMock()
    repo.select_gossip_secret = AsyncMock(return_value=None)
    repo.log_gossip = AsyncMock()
    repo.propagate_secret = AsyncMock()
    repo.create_rumor = AsyncMock(return_value="r-1")
    repo.believe_rumor = AsyncMock()
    return repo


def _make_handler(repo: MagicMock) -> GossipHandler:
    return GossipHandler(
        settings=_make_settings(),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
        gossip_repo=repo,
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gossip_tick_exactly_1_batch_read_for_3_pairs():
    """For 3 pairs the handler must call select_batch_event_trust exactly once."""
    n_pairs = 3
    pairs = _make_pairs(n_pairs)
    batch_rows = _make_batch_rows(n_pairs)
    repo = _make_repo(batch_rows)
    handler = _make_handler(repo)

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        await handler.run_tick(tick_id=1)

    repo.select_batch_event_trust.assert_called_once()
    repo.write_batch_knowledge_propagation.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_tick_result_counts_match_pairs():
    """run_tick must return propagated == number of pairs with valid events."""
    n_pairs = 4
    pairs = _make_pairs(n_pairs)
    batch_rows = _make_batch_rows(n_pairs)
    repo = _make_repo(batch_rows)
    handler = _make_handler(repo)

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result = await handler.run_tick(tick_id=5)

    assert result["propagated"] == n_pairs
    assert result["pairs"] == n_pairs
    assert result["tick_id"] == 5


@pytest.mark.asyncio
async def test_gossip_tick_skips_pairs_with_no_event():
    """Pairs for which no event is returned must be skipped (propagated not incremented)."""
    pairs = _make_pairs(3)
    # Only 2 of the 3 pairs have events
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
    repo = _make_repo(batch_rows)
    handler = _make_handler(repo)

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result = await handler.run_tick(tick_id=1)

    assert result["propagated"] == 2
    assert result["pairs"] == 3


@pytest.mark.asyncio
async def test_gossip_tick_swallows_session_kwarg():
    """run_tick must accept and silently discard a session= kwarg (Wave-5 cleanup guard)."""
    pairs = _make_pairs(1)
    batch_rows = _make_batch_rows(1)
    repo = _make_repo(batch_rows)
    handler = _make_handler(repo)

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result = await handler.run_tick(session=object(), tick_id=7)

    assert result["tick_id"] == 7
