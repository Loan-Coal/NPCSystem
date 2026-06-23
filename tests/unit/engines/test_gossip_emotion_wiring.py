"""
Unit tests for GossipHandler × EmotionUpdater wiring (S10.2).

Verifies that GossipHandler calls emotion_updater.apply_event_shock when
event severity >= RUMOR_EMOTION_SEVERITY_THRESHOLD, and does NOT call it
for low-severity events or when no emotion_updater is wired.

Updated for SEV-24: uses GossipGraphPort mock instead of patching module-level graph fns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_handler import GossipHandler


def _make_settings(emotion_threshold: int = 50):
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = 50
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = emotion_threshold
    return s


def _make_weight_config():
    cfg = MagicMock()
    cfg.hostile_distortion_factor = 1.0
    return cfg


def _make_repo(batch_row: list[dict]) -> MagicMock:
    """Return a mock GossipGraphPort pre-configured for one-pair tick tests."""
    repo = MagicMock()
    repo.select_batch_event_trust = AsyncMock(return_value=batch_row)
    repo.write_batch_knowledge_propagation = AsyncMock()
    repo.create_rumor = AsyncMock(return_value="r-1")
    repo.believe_rumor = AsyncMock()
    repo.select_gossip_secret = AsyncMock(return_value=None)
    repo.log_gossip = AsyncMock()
    repo.propagate_secret = AsyncMock()
    return repo


def _make_handler(emotion_updater=None, emotion_threshold: int = 50, repo=None):
    return GossipHandler(
        settings=_make_settings(emotion_threshold),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
        emotion_updater=emotion_updater,
        gossip_repo=repo,
    )


def _batch_row(severity: int) -> list[dict]:
    return [
        {
            "sharer_id": "sharer-1",
            "receiver_id": "receiver-1",
            "event_id": "e-rumor",
            "summary": "The captain is a traitor",
            "severity": severity,
            "is_canonical": False,
            "trust": 50,
        }
    ]


_PAIRS = [({"id": "sharer-1", "honesty": 50}, {"id": "receiver-1"}, "loc-1", {"best_standing": None})]


@pytest.mark.asyncio
async def test_emotion_shock_called_for_high_severity():
    """apply_event_shock must be called when severity >= threshold."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    repo = _make_repo(_batch_row(75))

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50, repo=repo)
        await handler.run_tick(tick_id=10)

    emotion_updater.apply_event_shock.assert_called_once_with(npc_id="receiver-1", severity=75)


@pytest.mark.asyncio
async def test_emotion_shock_not_called_for_low_severity():
    """apply_event_shock must NOT be called when severity < threshold."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    repo = _make_repo(_batch_row(30))

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50, repo=repo)
        await handler.run_tick(tick_id=10)

    emotion_updater.apply_event_shock.assert_not_called()


@pytest.mark.asyncio
async def test_emotion_shock_skipped_when_no_updater():
    """run_tick must not crash when emotion_updater=None for high-severity events."""
    repo = _make_repo(_batch_row(90))

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        handler = _make_handler(emotion_updater=None, emotion_threshold=50, repo=repo)
        result = await handler.run_tick(tick_id=10)

    assert result["propagated"] == 1


@pytest.mark.asyncio
async def test_emotion_shock_at_exact_threshold():
    """apply_event_shock must be called when severity == threshold (inclusive)."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    repo = _make_repo(_batch_row(50))

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50, repo=repo)
        await handler.run_tick(tick_id=10)

    emotion_updater.apply_event_shock.assert_called_once_with(npc_id="receiver-1", severity=50)
