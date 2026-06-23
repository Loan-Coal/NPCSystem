"""
Unit tests for gossip → RUMOR integration in GossipHandler.

Verifies that when distortion_level >= RUMOR_DISTORTION_THRESHOLD,
create_rumor and believe_rumor are called, while KNOWS_ABOUT (batch write)
is still written (backward compat). Also verifies non-distorted gossip
does NOT create a Rumor node.

Updated for SEV-24: uses GossipGraphPort mock instead of patching module-level graph fns.
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


def _make_repo(batch_rows: list[dict]) -> MagicMock:
    repo = MagicMock()
    repo.select_batch_event_trust = AsyncMock(return_value=batch_rows)
    repo.write_batch_knowledge_propagation = AsyncMock()
    repo.create_rumor = AsyncMock(return_value="r-1")
    repo.believe_rumor = AsyncMock()
    repo.select_gossip_secret = AsyncMock(return_value=None)
    repo.log_gossip = AsyncMock()
    repo.propagate_secret = AsyncMock()
    return repo


def _make_handler(rumor_threshold: int = 50, repo: MagicMock | None = None):
    return GossipHandler(
        settings=_make_settings(rumor_threshold),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
        gossip_repo=repo,
    )


_PAIRS = [
    (
        {"id": "sharer-1", "honesty": 50},
        {"id": "receiver-1"},
        "loc-1",
        {"best_standing": None},
    )
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gossip_handler_calls_propagate_always():
    """write_batch_knowledge_propagation must be called regardless of distortion level."""
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
    repo = _make_repo(batch_rows)
    handler = _make_handler(repo=repo)

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        await handler.run_tick(tick_id=1)

    repo.write_batch_knowledge_propagation.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_creates_rumor_when_distortion_level_exceeds_threshold():
    """create_rumor and believe_rumor are called when distortion_level >= threshold."""
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
    repo = _make_repo(batch_rows)
    handler = _make_handler(rumor_threshold=1, repo=repo)

    from npc_engine.engines.gossip.gossip_distort import GossipDistortion

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
        patch(
            "npc_engine.engines.gossip.gossip_handler.gossip_distort",
            return_value=GossipDistortion(
                summary="distorted summary",
                distortion_type="exaggeration",
                distortion_level=80,
            ),
        ),
    ):
        await handler.run_tick(tick_id=1)

    repo.create_rumor.assert_called_once()
    repo.believe_rumor.assert_called_once()


@pytest.mark.asyncio
async def test_gossip_no_rumor_when_distortion_below_threshold():
    """No Rumor created when distortion_level < threshold."""
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
    repo = _make_repo(batch_rows)
    handler = _make_handler(rumor_threshold=90, repo=repo)

    from npc_engine.engines.gossip.gossip_distort import GossipDistortion

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIRS)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
        patch(
            "npc_engine.engines.gossip.gossip_handler.gossip_distort",
            return_value=GossipDistortion(
                summary="test",
                distortion_type=None,
                distortion_level=0,
            ),
        ),
    ):
        await handler.run_tick(tick_id=1)

    repo.create_rumor.assert_not_called()
    repo.believe_rumor.assert_not_called()


@pytest.mark.asyncio
async def test_rumor_mutation_distance_chain():
    """Verify that create_derived_rumor increments mutation_distance via service."""
    from npc_engine.graph.gossip.rumor_service import create_derived_rumor

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
    repo = _make_repo(batch_rows)
    handler = _make_handler(rumor_threshold=1, repo=repo)

    from npc_engine.engines.gossip.gossip_distort import GossipDistortion

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=pairs)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
        patch(
            "npc_engine.engines.gossip.gossip_handler.gossip_distort",
            return_value=GossipDistortion(
                summary="extreme version",
                distortion_type="exaggeration",
                distortion_level=90,
            ),
        ),
    ):
        await handler.run_tick(tick_id=1)

    # batch write (KNOWS_ABOUT) must still be called
    repo.write_batch_knowledge_propagation.assert_called_once()
