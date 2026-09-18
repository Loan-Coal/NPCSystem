"""
Module: test_gossip_tick_query_count
Layer: tests/unit/graph
Purpose: Verifies that the gossip tick calls the corpus refresher exactly once per tick,
         regardless of how many pairs propagate. Before T7.3 the refresh was called once
         per pair (O(N) reconcile passes); after T7.3 it is called once per tick (O(1)).
Does NOT: run against a live Neo4j instance.
Dependencies: pytest, GossipHandler, _CountingRefresher
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.gossip.gossip_config import GossipWeightConfig
from npc_engine.engines.gossip.gossip_handler import GossipHandler

# Number of pairs to propagate in the test — must be > 1 to distinguish O(N) from O(1).
_N_PAIRS = 10


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


class _CountingRefresher:
    """Corpus refresher stub that counts per-pair and per-tick refresh calls.

    refresh()       → the old per-pair path (O(N) reconcile passes)
    refresh_batch() → the new per-tick path (O(1) reconcile pass)

    After T7.3 the gossip handler must call refresh_batch exactly once and
    must not call refresh at all.
    """

    def __init__(self) -> None:
        self.refresh_calls: int = 0
        self.refresh_batch_calls: int = 0

    async def refresh(self, node_id: str) -> bool:
        """Per-node refresh (old path — expected to be 0 calls after fix)."""
        self.refresh_calls += 1
        return True

    async def refresh_batch(self, node_ids: list[str]) -> int:
        """Batch refresh (new path — expected to be exactly 1 call after fix)."""
        self.refresh_batch_calls += 1
        return len(node_ids)


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.GOSSIP_DISTORTION_BASE = 0.1
    s.RUMOR_DISTORTION_THRESHOLD = 999  # never triggers rumor path
    s.RUMOR_EMOTION_SEVERITY_THRESHOLD = 999
    s.VECTOR_STORE_INCREMENTAL_UPSERT = True  # enables the batch refresh path
    return s


def _make_pairs(n: int) -> list[tuple[Any, Any, Any, Any]]:
    return [
        (
            {"id": f"sharer-{i}", "honesty": 50},
            {"id": f"receiver-{i}"},
            f"loc-{i}",
            {"best_standing": None},
        )
        for i in range(n)
    ]


def _make_batch_rows(n: int) -> list[dict[str, Any]]:
    return [
        {
            "sharer_id": f"sharer-{i}",
            "receiver_id": f"receiver-{i}",
            "event_id": f"event-{i}",
            "summary": "test event",
            "severity": 30,
            "is_canonical": False,
            "trust": 60,
        }
        for i in range(n)
    ]


def _make_gossip_repo(n: int) -> MagicMock:
    repo = MagicMock()
    repo.select_batch_event_trust = AsyncMock(return_value=_make_batch_rows(n))
    repo.write_batch_knowledge_propagation = AsyncMock()
    repo.log_gossip = AsyncMock()
    repo.select_gossip_secret = AsyncMock(return_value=None)
    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconcile_count_does_not_scale_with_pairs() -> None:
    """Corpus refresher must be invoked once per tick, not once per pair.

    Before T7.3: refresh(receiver_id) was called _N_PAIRS times, driving an
    equally-sized number of reconcile_in_session passes — O(N) reconciliation.

    After T7.3: refresh_batch(receiver_ids) is called once per tick — O(1)
    reconciliation regardless of pair count.

    RED anchor: today the handler never calls refresh_batch, so refresh_batch_calls==0
    and the assertion 'total == 1' fails with count==_N_PAIRS from the per-pair path.
    """
    refresher = _CountingRefresher()
    embedding_index = MagicMock()
    embedding_index.invalidate = AsyncMock()

    handler = GossipHandler(
        settings=_make_settings(),
        embedding_index=embedding_index,
        weight_config=GossipWeightConfig(),
        corpus_refresher=refresher,
        gossip_repo=_make_gossip_repo(_N_PAIRS),
    )

    with patch(
        "npc_engine.engines.gossip.gossip_handler.select_pairs",
        new=AsyncMock(return_value=_make_pairs(_N_PAIRS)),
    ):
        await handler.run_tick(tick_id=1)

    total_refresh_invocations = refresher.refresh_calls + refresher.refresh_batch_calls
    assert total_refresh_invocations == 1, (
        f"Expected exactly 1 refresh invocation per tick for {_N_PAIRS} pairs, "
        f"got refresh={refresher.refresh_calls} (per-pair) "
        f"+ refresh_batch={refresher.refresh_batch_calls} (per-tick) "
        f"= {total_refresh_invocations}. "
        f"The reconcile count must be O(1), not O(N)."
    )
    assert refresher.refresh_batch_calls == 1, (
        f"refresh_batch must be called exactly once (got {refresher.refresh_batch_calls}); "
        f"per-pair refresh calls: {refresher.refresh_calls}"
    )
