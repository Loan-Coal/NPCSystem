"""
Unit tests for gossip → RUMOR integration in GossipHandler.

Verifies that when distortion_level >= RUMOR_DISTORTION_THRESHOLD,
create_rumor and believe_rumor are called, while KNOWS_ABOUT (propagate)
is still written (backward compat). Also verifies non-distorted gossip
does NOT create a Rumor node.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_handler import GossipHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(rumor_threshold: int = 50):
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = rumor_threshold
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


def _make_session():
    session = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gossip_handler_calls_propagate_always():
    """propagate (KNOWS_ABOUT) must be called regardless of distortion level."""
    handler = _make_handler()
    session = _make_session()

    pairs = [
        (
            {"id": "sharer-1", "honesty": 50},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]

    with patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs), \
         patch("npc_engine.engines.gossip.gossip_handler.propagate", new_callable=AsyncMock) as mock_propagate, \
         patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random:

        mock_random.random.return_value = 1.0  # skip secret propagation branch

        event_record = MagicMock()
        event_record.__getitem__ = lambda s, k: {"event_id": "e-1", "summary": "test", "severity": 30}[k]
        trust_record = MagicMock()
        trust_record.__getitem__ = lambda s, k: {"trust": 60}[k]

        call_count = [0]
        async def _run_side(query, **kwargs):
            res = AsyncMock()
            if call_count[0] == 0:
                res.single = AsyncMock(return_value=event_record)
            else:
                res.single = AsyncMock(return_value=trust_record)
            call_count[0] += 1
            return res

        session.run = AsyncMock(side_effect=_run_side)

        await handler.run_tick(session=session, tick_id=1)
        mock_propagate.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_creates_rumor_when_distortion_level_exceeds_threshold():
    """create_rumor and believe_rumor are called when distortion_level >= threshold."""
    handler = _make_handler(rumor_threshold=1)  # threshold=1 so any distortion triggers
    session = _make_session()

    pairs = [
        (
            {"id": "sharer-1", "honesty": 0},  # low honesty → high distortion
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]

    with patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs), \
         patch("npc_engine.engines.gossip.gossip_handler.propagate", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1") as mock_create, \
         patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock) as mock_believe:

        event_record = MagicMock()
        event_record.__getitem__ = lambda s, k: {"event_id": "e-1", "summary": "awful things", "severity": 90}[k]
        # trust record
        trust_record = MagicMock()
        trust_record.__getitem__ = lambda s, k: {"trust": 10}[k]

        call_count = [0]
        async def _run_side(query, **kwargs):
            res = AsyncMock()
            if call_count[0] == 0:
                res.single = AsyncMock(return_value=event_record)
            else:
                res.single = AsyncMock(return_value=trust_record)
            call_count[0] += 1
            return res

        session.run = AsyncMock(side_effect=_run_side)

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
    session = _make_session()

    pairs = [
        (
            {"id": "sharer-1", "honesty": 50},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]

    with patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs), \
         patch("npc_engine.engines.gossip.gossip_handler.propagate", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock) as mock_create, \
         patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock) as mock_believe:

        event_record = MagicMock()
        event_record.__getitem__ = lambda s, k: {"event_id": "e-1", "summary": "test", "severity": 30}[k]
        trust_record = MagicMock()
        trust_record.__getitem__ = lambda s, k: {"trust": 80}[k]

        call_count = [0]
        async def _run_side(query, **kwargs):
            res = AsyncMock()
            if call_count[0] == 0:
                res.single = AsyncMock(return_value=event_record)
            else:
                res.single = AsyncMock(return_value=trust_record)
            call_count[0] += 1
            return res

        session.run = AsyncMock(side_effect=_run_side)

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
    """KNOWS_ABOUT (propagate) must still be called — backward compat."""
    handler = _make_handler(rumor_threshold=1)
    session = _make_session()

    pairs = [
        (
            {"id": "sharer-1", "honesty": 0},
            {"id": "receiver-1"},
            "loc-1",
            {"best_standing": None},
        )
    ]

    with patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new_callable=AsyncMock, return_value=pairs), \
         patch("npc_engine.engines.gossip.gossip_handler.propagate", new_callable=AsyncMock) as mock_propagate, \
         patch("npc_engine.engines.gossip.gossip_handler.log_gossip", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.create_rumor", new_callable=AsyncMock, return_value="r-1"), \
         patch("npc_engine.engines.gossip.gossip_handler.believe_rumor", new_callable=AsyncMock), \
         patch("npc_engine.engines.gossip.gossip_handler.random") as mock_random:

        mock_random.random.return_value = 1.0  # skip secret propagation branch

        event_record = MagicMock()
        event_record.__getitem__ = lambda s, k: {"event_id": "e-1", "summary": "extreme", "severity": 95}[k]
        trust_record = MagicMock()
        trust_record.__getitem__ = lambda s, k: {"trust": 5}[k]

        call_count = [0]
        async def _run_side(query, **kwargs):
            res = AsyncMock()
            if call_count[0] == 0:
                res.single = AsyncMock(return_value=event_record)
            else:
                res.single = AsyncMock(return_value=trust_record)
            call_count[0] += 1
            return res

        session.run = AsyncMock(side_effect=_run_side)

        with patch("npc_engine.engines.gossip.gossip_handler.gossip_distort") as mock_distort:
            from npc_engine.engines.gossip.gossip_distort import GossipDistortion
            mock_distort.return_value = GossipDistortion(
                summary="extreme version",
                distortion_type="exaggeration",
                distortion_level=90,
            )
            await handler.run_tick(session=session, tick_id=1)

        # propagate (KNOWS_ABOUT) must still be called
        mock_propagate.assert_called_once()
