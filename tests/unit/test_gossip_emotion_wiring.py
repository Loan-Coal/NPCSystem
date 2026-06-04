"""
Unit tests for GossipHandler × EmotionUpdater wiring (S10.2).

Verifies that GossipHandler calls emotion_updater.apply_event_shock when
event severity >= RUMOR_EMOTION_SEVERITY_THRESHOLD, and does NOT call it
for low-severity events or when no emotion_updater is wired.
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


def _make_handler(emotion_updater=None, emotion_threshold: int = 50):
    return GossipHandler(
        settings=_make_settings(emotion_threshold),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
        emotion_updater=emotion_updater,
    )


def _make_mock_session() -> AsyncMock:
    return AsyncMock()


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


@pytest.mark.asyncio
async def test_emotion_shock_called_for_high_severity():
    """apply_event_shock must be called when severity >= threshold."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50)

    pairs = [
        ({"id": "sharer-1", "honesty": 50}, {"id": "receiver-1"}, "loc-1", {"best_standing": None})
    ]
    session = _make_mock_session()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs),
        patch("npc_engine.engines.gossip.gossip_handler.select_batch_event_trust", new_callable=AsyncMock, return_value=_batch_row(75)),
        patch("npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1"),
        patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.select_gossip_secret", new_callable=AsyncMock, return_value=None),
        patch("npc_engine.engines.gossip.gossip_handler.propagate_secret", new_callable=AsyncMock),
    ):

        await handler.run_tick(session=session, tick_id=10)

    emotion_updater.apply_event_shock.assert_called_once_with(npc_id="receiver-1", severity=75)


@pytest.mark.asyncio
async def test_emotion_shock_not_called_for_low_severity():
    """apply_event_shock must NOT be called when severity < threshold."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50)

    pairs = [
        ({"id": "sharer-1", "honesty": 50}, {"id": "receiver-1"}, "loc-1", {"best_standing": None})
    ]
    session = _make_mock_session()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs),
        patch("npc_engine.engines.gossip.gossip_handler.select_batch_event_trust", new_callable=AsyncMock, return_value=_batch_row(30)),
        patch("npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1"),
        patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.select_gossip_secret", new_callable=AsyncMock, return_value=None),
        patch("npc_engine.engines.gossip.gossip_handler.propagate_secret", new_callable=AsyncMock),
    ):

        await handler.run_tick(session=session, tick_id=10)

    emotion_updater.apply_event_shock.assert_not_called()


@pytest.mark.asyncio
async def test_emotion_shock_skipped_when_no_updater():
    """run_tick must not crash when emotion_updater=None for high-severity events."""
    handler = _make_handler(emotion_updater=None, emotion_threshold=50)

    pairs = [
        ({"id": "sharer-1", "honesty": 50}, {"id": "receiver-1"}, "loc-1", {"best_standing": None})
    ]
    session = _make_mock_session()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs),
        patch("npc_engine.engines.gossip.gossip_handler.select_batch_event_trust", new_callable=AsyncMock, return_value=_batch_row(90)),
        patch("npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1"),
        patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.select_gossip_secret", new_callable=AsyncMock, return_value=None),
        patch("npc_engine.engines.gossip.gossip_handler.propagate_secret", new_callable=AsyncMock),
    ):

        result = await handler.run_tick(session=session, tick_id=10)

    assert result["propagated"] == 1


@pytest.mark.asyncio
async def test_emotion_shock_at_exact_threshold():
    """apply_event_shock must be called when severity == threshold (inclusive)."""
    emotion_updater = MagicMock()
    emotion_updater.apply_event_shock = AsyncMock()
    handler = _make_handler(emotion_updater=emotion_updater, emotion_threshold=50)

    pairs = [
        ({"id": "sharer-1", "honesty": 50}, {"id": "receiver-1"}, "loc-1", {"best_standing": None})
    ]
    session = _make_mock_session()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs),
        patch("npc_engine.engines.gossip.gossip_handler.select_batch_event_trust", new_callable=AsyncMock, return_value=_batch_row(50)),
        patch("npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1"),
        patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.select_gossip_secret", new_callable=AsyncMock, return_value=None),
        patch("npc_engine.engines.gossip.gossip_handler.propagate_secret", new_callable=AsyncMock),
    ):

        await handler.run_tick(session=session, tick_id=10)

    emotion_updater.apply_event_shock.assert_called_once_with(npc_id="receiver-1", severity=50)
