"""
Module: test_gossip_determinism
Layer: tests/unit
Purpose: Verify that GossipHandler.run_tick() exposes seeds_used in its return value,
         and that identical tick_id inputs produce identical seeds while differing tick_ids
         produce different seeds.
Dependencies: npc_engine.engines.gossip.gossip_handler
Used by: pytest
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


def _make_handler() -> GossipHandler:
    return GossipHandler(
        settings=_make_settings(),
        embedding_index=MagicMock(),
        weight_config=_make_weight_config(),
    )


# One pair: captain_sorn shares with mira_innkeeper
_PAIR = [
    (
        {"id": "captain_sorn", "honesty": 70},
        {"id": "mira_innkeeper"},
        "tavern",
        {"best_standing": None},
    )
]

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

# Patch targets for the new batch-query version of gossip_handler
_PATCH_SELECT_PAIRS = "npc_engine.engines.gossip.gossip_handler.select_pairs"
_PATCH_BATCH_READ = "npc_engine.engines.gossip.gossip_handler.select_batch_event_trust"
_PATCH_BATCH_WRITE = "npc_engine.engines.gossip.gossip_handler.write_batch_knowledge_propagation"
_PATCH_LOG_GOSSIP = "npc_engine.engines.gossip.gossip_handler.log_gossip"
_PATCH_INVALIDATE = "npc_engine.engines.gossip.gossip_handler.invalidate_embedding_safely"
_PATCH_CREATE_RUMOR = "npc_engine.engines.gossip.gossip_handler.create_rumor"
_PATCH_BELIEVE_RUMOR = "npc_engine.engines.gossip.gossip_handler.believe_rumor"
_PATCH_SELECT_SECRET = "npc_engine.engines.gossip.gossip_handler.select_gossip_secret"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeds_used_key_in_run_tick_result() -> None:
    handler = _make_handler()
    session = AsyncMock()

    with (
        patch(_PATCH_SELECT_PAIRS, new_callable=AsyncMock, return_value=_PAIR),
        patch(_PATCH_BATCH_READ, new_callable=AsyncMock, return_value=[_BATCH_ROW]),
        patch(_PATCH_BATCH_WRITE, new_callable=AsyncMock),
        patch(_PATCH_LOG_GOSSIP, new_callable=AsyncMock),
        patch(_PATCH_INVALIDATE, new_callable=AsyncMock),
        patch(_PATCH_CREATE_RUMOR, new_callable=AsyncMock, return_value="rumor-1"),
        patch(_PATCH_BELIEVE_RUMOR, new_callable=AsyncMock),
        patch(_PATCH_SELECT_SECRET, new_callable=AsyncMock, return_value=None),
    ):
        result = await handler.run_tick(session=session, tick_id=42)

    assert "seeds_used" in result, "run_tick() must return a 'seeds_used' key"
    assert isinstance(result["seeds_used"], dict)


@pytest.mark.asyncio
async def test_same_tick_override_produces_same_seeds() -> None:
    handler = _make_handler()
    session = AsyncMock()

    with (
        patch(_PATCH_SELECT_PAIRS, new_callable=AsyncMock, return_value=_PAIR),
        patch(_PATCH_BATCH_READ, new_callable=AsyncMock, return_value=[_BATCH_ROW]),
        patch(_PATCH_BATCH_WRITE, new_callable=AsyncMock),
        patch(_PATCH_LOG_GOSSIP, new_callable=AsyncMock),
        patch(_PATCH_INVALIDATE, new_callable=AsyncMock),
        patch(_PATCH_CREATE_RUMOR, new_callable=AsyncMock, return_value="rumor-1"),
        patch(_PATCH_BELIEVE_RUMOR, new_callable=AsyncMock),
        patch(_PATCH_SELECT_SECRET, new_callable=AsyncMock, return_value=None),
    ):
        result_a = await handler.run_tick(session=session, tick_id=42)

    # Reset lock for second run
    handler._lock = asyncio.Lock()

    with (
        patch(_PATCH_SELECT_PAIRS, new_callable=AsyncMock, return_value=_PAIR),
        patch(_PATCH_BATCH_READ, new_callable=AsyncMock, return_value=[_BATCH_ROW]),
        patch(_PATCH_BATCH_WRITE, new_callable=AsyncMock),
        patch(_PATCH_LOG_GOSSIP, new_callable=AsyncMock),
        patch(_PATCH_INVALIDATE, new_callable=AsyncMock),
        patch(_PATCH_CREATE_RUMOR, new_callable=AsyncMock, return_value="rumor-1"),
        patch(_PATCH_BELIEVE_RUMOR, new_callable=AsyncMock),
        patch(_PATCH_SELECT_SECRET, new_callable=AsyncMock, return_value=None),
    ):
        result_b = await handler.run_tick(session=session, tick_id=42)

    assert result_a["seeds_used"] == result_b["seeds_used"], (
        "Same tick_id must produce identical seeds_used"
    )


@pytest.mark.asyncio
async def test_different_tick_id_produces_different_seeds() -> None:
    handler = _make_handler()
    session = AsyncMock()

    with (
        patch(_PATCH_SELECT_PAIRS, new_callable=AsyncMock, return_value=_PAIR),
        patch(_PATCH_BATCH_READ, new_callable=AsyncMock, return_value=[_BATCH_ROW]),
        patch(_PATCH_BATCH_WRITE, new_callable=AsyncMock),
        patch(_PATCH_LOG_GOSSIP, new_callable=AsyncMock),
        patch(_PATCH_INVALIDATE, new_callable=AsyncMock),
        patch(_PATCH_CREATE_RUMOR, new_callable=AsyncMock, return_value="rumor-1"),
        patch(_PATCH_BELIEVE_RUMOR, new_callable=AsyncMock),
        patch(_PATCH_SELECT_SECRET, new_callable=AsyncMock, return_value=None),
    ):
        result_42 = await handler.run_tick(session=session, tick_id=42)

    handler._lock = asyncio.Lock()

    with (
        patch(_PATCH_SELECT_PAIRS, new_callable=AsyncMock, return_value=_PAIR),
        patch(_PATCH_BATCH_READ, new_callable=AsyncMock, return_value=[_BATCH_ROW]),
        patch(_PATCH_BATCH_WRITE, new_callable=AsyncMock),
        patch(_PATCH_LOG_GOSSIP, new_callable=AsyncMock),
        patch(_PATCH_INVALIDATE, new_callable=AsyncMock),
        patch(_PATCH_CREATE_RUMOR, new_callable=AsyncMock, return_value="rumor-1"),
        patch(_PATCH_BELIEVE_RUMOR, new_callable=AsyncMock),
        patch(_PATCH_SELECT_SECRET, new_callable=AsyncMock, return_value=None),
    ):
        result_43 = await handler.run_tick(session=session, tick_id=43)

    pair_key = "captain_sorn→mira_innkeeper"
    assert pair_key in result_42["seeds_used"], f"Expected pair key '{pair_key}' in seeds_used"
    assert result_42["seeds_used"][pair_key] != result_43["seeds_used"][pair_key], (
        "Different tick_id must produce different seeds"
    )
