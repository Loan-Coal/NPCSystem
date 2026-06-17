"""
test_pair_selector_coverage.py - Unit tests for engines.gossip.pair_selector.

Does NOT: execute graph I/O against a real database.

Dependencies injected: mock GossipGraphPort (SEV-24).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.pair_selector import select_pairs

_DEFAULT_CONFIG = GossipWeightConfig()


def _make_row(a_id: str, b_id: str, gossipy_a: int = 50, gossipy_b: int = 50) -> dict:
    """Build a minimal data row as returned by CYPHER_GOSSIP_PAIRS."""
    return {
        "a": {"id": a_id, "gossipy": gossipy_a},
        "b": {"id": b_id, "gossipy": gossipy_b},
        "loc": {"id": "tavern"},
        "a_faction_ids": [],
        "b_faction_ids": [],
        "best_standing": None,
    }


def _make_repo(rows: list[dict]) -> MagicMock:
    """Return a mock GossipGraphPort pre-configured for pair selection tests."""
    repo = MagicMock()
    repo.fetch_gossip_pairs = AsyncMock(return_value=rows)
    repo.get_goals_for_character = AsyncMock(return_value=[])
    repo.fetch_known_node_ids = AsyncMock(return_value=set())
    return repo


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_pairs_deterministic_same_data() -> None:
    """Identical input data must produce identical pair ordering on every call."""
    rows = [_make_row("npc_a", "npc_b"), _make_row("npc_c", "npc_d", gossipy_a=80)]
    repo1 = _make_repo(rows)
    first = await select_pairs(repo=repo1, max_pairs=10, weight_config=_DEFAULT_CONFIG)

    repo2 = _make_repo(rows)
    second = await select_pairs(repo=repo2, max_pairs=10, weight_config=_DEFAULT_CONFIG)

    first_ids = [(p[0]["id"], p[1]["id"]) for p in first]
    second_ids = [(p[0]["id"], p[1]["id"]) for p in second]
    assert first_ids == second_ids, "pair ordering must be deterministic"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_pairs_higher_gossipy_ranks_first() -> None:
    """Pair with higher combined gossipy score should rank before low-gossipy pair."""
    high_pair = _make_row("high_a", "high_b", gossipy_a=90, gossipy_b=90)
    low_pair = _make_row("low_a", "low_b", gossipy_a=10, gossipy_b=10)
    rows = [low_pair, high_pair]  # deliberately unsorted
    repo = _make_repo(rows)

    result = await select_pairs(repo=repo, max_pairs=10, weight_config=_DEFAULT_CONFIG)

    assert result[0][0]["id"] == "high_a", "highest gossipy pair must be ranked first"


# ---------------------------------------------------------------------------
# max_pairs limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_pairs_max_pairs_limit() -> None:
    """select_pairs must never return more than max_pairs pairs."""
    rows = [_make_row(f"a_{i}", f"b_{i}") for i in range(10)]
    repo = _make_repo(rows)

    result = await select_pairs(repo=repo, max_pairs=3, weight_config=_DEFAULT_CONFIG)

    assert len(result) <= 3


# ---------------------------------------------------------------------------
# Empty result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_pairs_empty_returns_empty() -> None:
    """When there are no co-located NPCs, result must be empty."""
    repo = _make_repo([])
    result = await select_pairs(repo=repo, max_pairs=10, weight_config=_DEFAULT_CONFIG)
    assert result == []


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_pairs_returns_correct_tuple_shape() -> None:
    """Each result element must be a 4-tuple: (sharer, receiver, location, faction_ctx)."""
    rows = [_make_row("npc_a", "npc_b")]
    repo = _make_repo(rows)

    result = await select_pairs(repo=repo, max_pairs=5, weight_config=_DEFAULT_CONFIG)

    assert len(result) == 1
    sharer, receiver, location, faction_ctx = result[0]
    assert sharer["id"] == "npc_a"
    assert receiver["id"] == "npc_b"
    assert "a_faction_ids" in faction_ctx
    assert "b_faction_ids" in faction_ctx
    assert "best_standing" in faction_ctx
