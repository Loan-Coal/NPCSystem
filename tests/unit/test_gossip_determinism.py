"""
Module: test_gossip_determinism
Layer: tests/unit
Purpose: Verify that GossipHandler.run_tick() exposes seeds_used in its return value,
         and that identical tick_id inputs produce identical seeds while differing tick_ids
         produce different seeds.
Dependencies: npc_engine.engines.gossip.gossip_handler
Used by: pytest

Updated for SEV-24: uses GossipGraphPort mock instead of patching module-level graph fns.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_handler import GossipHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings() -> MagicMock:
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = 50
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = 70
    return s


def _make_weight_config() -> MagicMock:
    cfg = MagicMock()
    cfg.hostile_distortion_factor = 1.0
    return cfg


_EVENT_SUMMARY = "War is coming from the north."
_BATCH_ROW = {
    "sharer_id": "captain_sorn",
    "receiver_id": "mira_innkeeper",
    "event_id": "northern_war_begins",
    "summary": _EVENT_SUMMARY,
    "severity": 80,
    "trust": 60,
    "is_canonical": False,
}

_PAIR = [
    (
        {"id": "captain_sorn", "honesty": 70},
        {"id": "mira_innkeeper"},
        "tavern",
        {"best_standing": None},
    )
]


def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo.select_batch_event_trust = AsyncMock(return_value=[_BATCH_ROW])
    repo.write_batch_knowledge_propagation = AsyncMock()
    repo.create_rumor = AsyncMock(return_value="rumor-1")
    repo.believe_rumor = AsyncMock()
    repo.select_gossip_secret = AsyncMock(return_value=None)
    repo.log_gossip = AsyncMock()
    repo.propagate_secret = AsyncMock()
    return repo


def _make_handler() -> GossipHandler:
    return GossipHandler(
        settings=_make_settings(),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
        gossip_repo=_make_repo(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeds_used_key_in_run_tick_result() -> None:
    handler = _make_handler()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIR)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result = await handler.run_tick(tick_id=42)

    assert "seeds_used" in result, "run_tick() must return a 'seeds_used' key"
    assert isinstance(result["seeds_used"], dict)


@pytest.mark.asyncio
async def test_same_tick_override_produces_same_seeds() -> None:
    handler = _make_handler()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIR)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result_a = await handler.run_tick(tick_id=42)

    # Reset lock for second run
    handler._lock = asyncio.Lock()
    handler._gossip_repo = _make_repo()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIR)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result_b = await handler.run_tick(tick_id=42)

    assert result_a["seeds_used"] == result_b["seeds_used"], (
        "Same tick_id must produce identical seeds_used"
    )


@pytest.mark.asyncio
async def test_different_tick_id_produces_different_seeds() -> None:
    handler = _make_handler()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIR)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result_42 = await handler.run_tick(tick_id=42)

    handler._lock = asyncio.Lock()
    handler._gossip_repo = _make_repo()

    with (
        patch("npc_engine.engines.gossip.gossip_handler.select_pairs", new=AsyncMock(return_value=_PAIR)),
        patch("npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely", new=AsyncMock()),
    ):
        result_43 = await handler.run_tick(tick_id=43)

    pair_key = "captain_sorn→mira_innkeeper"
    assert pair_key in result_42["seeds_used"], f"Expected pair key '{pair_key}' in seeds_used"
    assert result_42["seeds_used"][pair_key] != result_43["seeds_used"][pair_key], (
        "Different tick_id must produce different seeds"
    )
