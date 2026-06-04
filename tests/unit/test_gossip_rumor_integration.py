"""
Unit tests for gossip → RUMOR integration in GossipHandler.

Verifies that when distortion_level >= RUMOR_DISTORTION_THRESHOLD,
create_rumor and believe_rumor are called, while KNOWS_ABOUT (propagate)
is still written (backward compat). Also verifies non-distorted gossip
does NOT create a Rumor node.

Updated for SEV-29: uses batch interface (select_batch_event_trust +
write_batch_knowledge_propagation instead of per-pair calls).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_handler import GossipHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(rumor_threshold: int = 50, rumor_emotion_threshold: int = 999):
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = rumor_threshold
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = rumor_emotion_threshold
    return s


def _make_weight_config():
    cfg = MagicMock()
    cfg.hostile_distortion_factor = 1.0
    return cfg


def _make_handler(rumor_threshold: int = 50):
    return GossipHandler(
        settings=_make_settings(rumor_threshold),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
    )


def _make_async_iter(records: list[dict]):
    async def _gen():
        for r in records:
            yield r

    return _gen()


def _batch_session(batch_rows: list[dict]) -> AsyncMock:
    """Return a session whose first run() call returns batch_rows via async iter."""
    session = AsyncMock()
    read_result = AsyncMock()
    read_result.__aiter__ = MagicMock(return_value=_make_async_iter(batch_rows))
    read_result.consume = AsyncMock()
    write_result = AsyncMock()
    write_result.consume = AsyncMock()
    session.run = AsyncMock(side_effect=[read_result, write_result])
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gossip_handler_calls_propagate_always():
    """write_batch_knowledge_propagation must be called regardless of distortion level."""
    handler = _make_handler()

    pairs = [
        (
            {"id": "sharer-1", "honesty": 50},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]
    batch_rows = [
        {
            "sharer_id": "sharer-1",
            "receiver_id": "receiver-1",
            "event_id": "e-1",
            "summary": "test",
            "severity": 30,
            "is_canonical": False,
            "trust": 60,
        }
    ]
    session = _batch_session(batch_rows)

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation",
            new_callable=AsyncMock,
        ) as mock_batch_write,
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random,
    ):
        mock_random.random.return_value = 1.0  # skip secret propagation

        await handler.run_tick(session=session, tick_id=1)
        mock_batch_write.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_creates_rumor_when_distortion_level_exceeds_threshold():
    """create_rumor and believe_rumor are called when distortion_level >= threshold."""
    handler = _make_handler(rumor_threshold=1)

    pairs = [
        (
            {"id": "sharer-1", "honesty": 0},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]
    batch_rows = [
        {
            "sharer_id": "sharer-1",
            "receiver_id": "receiver-1",
            "event_id": "e-1",
            "summary": "awful things",
            "severity": 90,
            "is_canonical": False,
            "trust": 10,
        }
    ]
    session = _batch_session(batch_rows)

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.create_rumor",
            new_callable=AsyncMock,
            return_value="r-1",
        ) as mock_create,
        patch(
            "npc_engine.engines.gossip.gossip_handler.believe_rumor",
            new_callable=AsyncMock,
        ) as mock_believe,
        patch("npc_engine.engines.gossip.gossip_handler.random.random", return_value=1.0),
    ):
        with patch("npc_engine.engines.gossip.gossip_handler.gossip_distort") as mock_distort:
            from npc_engine.engines.gossip.gossip_distort import GossipDistortion

            mock_distort.return_value = GossipDistortion(
                summary="distorted summary",
                distortion_type="exaggeration",
                distortion_level=80,
            )
            result = await handler.run_tick(session=session, tick_id=1)

    mock_create.assert_called_once()
    mock_believe.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_no_rumor_when_distortion_below_threshold():
    """No Rumor created when distortion_level < threshold."""
    handler = _make_handler(rumor_threshold=90)

    pairs = [
        (
            {"id": "sharer-1", "honesty": 50},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]
    batch_rows = [
        {
            "sharer_id": "sharer-1",
            "receiver_id": "receiver-1",
            "event_id": "e-1",
            "summary": "test",
            "severity": 30,
            "is_canonical": False,
            "trust": 80,
        }
    ]
    session = _batch_session(batch_rows)

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation",
            new_callable=AsyncMock,
        ),
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.create_rumor",
            new_callable=AsyncMock,
        ) as mock_create,
        patch(
            "npc_engine.engines.gossip.gossip_handler.believe_rumor",
            new_callable=AsyncMock,
        ) as mock_believe,
        patch("npc_engine.engines.gossip.gossip_handler.random.random", return_value=1.0),
    ):
        with patch("npc_engine.engines.gossip.gossip_handler.gossip_distort") as mock_distort:
            from npc_engine.engines.gossip.gossip_distort import GossipDistortion

            mock_distort.return_value = GossipDistortion(
                summary="test",
                distortion_type=None,
                distortion_level=0,
            )
            await handler.run_tick(session=session, tick_id=1)

    mock_create.assert_not_called()
    mock_believe.assert_not_called()


@pytest.mark.asyncio
async def test_rumor_mutation_distance_chain():
    """Verify that create_derived_rumor increments mutation_distance via service."""
    from npc_engine.graph.rumor_service import create_derived_rumor

    session = AsyncMock()
    parent_id = "rumor:root:event-1"
    derived_id = await create_derived_rumor(
        session,
        parent_rumor_id=parent_id,
        content="More distorted",
        mutation_type="role_swap",
        created_at_tick=10,
    )
    assert isinstance(derived_id, str)
    session.run.assert_called_once()
    call_kwargs = session.run.call_args.kwargs
    assert call_kwargs["parent_rumor_id"] == parent_id
    assert call_kwargs["mutation_type"] == "role_swap"


@pytest.mark.asyncio
async def test_knows_about_still_created_alongside_rumor():
    """write_batch_knowledge_propagation must still be called — backward compat."""
    handler = _make_handler(rumor_threshold=1)

    pairs = [
        (
            {"id": "sharer-1", "honesty": 0},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]
    batch_rows = [
        {
            "sharer_id": "sharer-1",
            "receiver_id": "receiver-1",
            "event_id": "e-1",
            "summary": "extreme",
            "severity": 95,
            "is_canonical": False,
            "trust": 5,
        }
    ]
    session = _batch_session(batch_rows)

    with (
        patch(
            "npc_engine.engines.gossip.gossip_handler.select_pairs",
            new_callable=AsyncMock,
            return_value=pairs,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation",
            new_callable=AsyncMock,
        ) as mock_batch_write,
        patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock),
        patch(
            "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely",
            new_callable=AsyncMock,
        ),
        patch(
            "npc_engine.engines.gossip.gossip_handler.create_rumor",
            new_callable=AsyncMock,
            return_value="r-1",
        ),
        patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock),
        patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random,
    ):
        mock_random.random.return_value = 1.0  # skip secret propagation

        with patch("npc_engine.engines.gossip.gossip_handler.gossip_distort") as mock_distort:
            from npc_engine.engines.gossip.gossip_distort import GossipDistortion

            mock_distort.return_value = GossipDistortion(
                summary="extreme version",
                distortion_type="exaggeration",
                distortion_level=90,
            )
            await handler.run_tick(session=session, tick_id=1)

    # batch write (KNOWS_ABOUT) must still be called
    mock_batch_write.assert_called_once()
