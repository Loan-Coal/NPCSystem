"""
Module: test_gossip_distortion_read_back
Layer: tests/unit/graph
Purpose: Verifies that the batch event-trust read query exposes k.distorted_summary from
         the KNOWS_ABOUT edge so gossip distortion accumulated over multiple hops is
         preserved on read rather than silently replaced by canonical Event.summary.
         Finding CR-L01-01 (review-2026-08/TRIAGE.md). DEC-284.
Does NOT: run against a live Neo4j instance.
Dependencies: pytest, gossip_batch_queries
"""
from __future__ import annotations

from typing import Any

import pytest

from npc_engine.graph.gossip.gossip_batch_queries import (
    CYPHER_BATCH_EVENT_TRUST,
    select_batch_event_trust,
)

_CANONICAL_SUMMARY = "The ambassador left the city without incident."
_HOP2_DISTORTED = "The ambassador was driven out in disgrace after a scandal!"


async def _aiter_rows(rows: list[dict[str, Any]]):  # type: ignore[return]
    """Yield rows as an async generator, simulating a Neo4j result cursor."""
    for row in rows:
        yield row


class _QueryAwareSession:
    """Fake Neo4j session whose rows depend on whether the query reads the edge field.

    Before fix: CYPHER_BATCH_EVENT_TRUST does not contain ``k.distorted_summary``, so
    the session returns canonical Event.summary — the bug.
    After fix: the query contains ``k.distorted_summary`` via coalesce, so the session
    returns the distorted edge text — the correct behaviour.
    """

    async def run(self, query: str, **_kw: Any) -> Any:
        """Return distorted rows only when the query exposes k.distorted_summary."""
        if "k.distorted_summary" in query:
            summary = _HOP2_DISTORTED
        else:
            summary = _CANONICAL_SUMMARY
        rows = [
            {
                "sharer_id": "npc_b",
                "receiver_id": "npc_c",
                "event_id": "event_1",
                "summary": summary,
                "severity": 60,
                "is_canonical": True,
                "trust": 55,
            }
        ]
        return _aiter_rows(rows)


# ---------------------------------------------------------------------------
# Query-string tests — RED anchor (fail today, pass after fix)
# ---------------------------------------------------------------------------


def test_event_trust_query_reads_edge_distorted_summary() -> None:
    """CYPHER_BATCH_EVENT_TRUST must select k.distorted_summary from the KNOWS_ABOUT edge.

    CYPHER_BATCH_PROPAGATE_KNOWLEDGE writes k.distorted_summary on every propagation hop.
    If the read query ignores it and returns best_event.summary instead, distortion is
    computed, written, and discarded — every NPC recounts the canonical text regardless
    of how many hops the gossip travelled. Finding CR-L01-01.
    """
    assert "k.distorted_summary" in CYPHER_BATCH_EVENT_TRUST, (
        "CYPHER_BATCH_EVENT_TRUST returns best_event.summary (canonical Event text), "
        "ignoring k.distorted_summary written by CYPHER_BATCH_PROPAGATE_KNOWLEDGE on "
        "every hop. Distortion is computed and discarded on every read. CR-L01-01."
    )


def test_event_trust_query_uses_coalesce_for_canonical_fallback() -> None:
    """Canonical Event.summary must be the coalesce fallback, not the primary source.

    First-hand witnesses have no distorted_summary on their KNOWS_ABOUT edge (they
    observed the event directly). coalesce ensures they still receive canonical text
    rather than null. Without coalesce, the fix would break first-hand accounts.
    """
    assert "coalesce" in CYPHER_BATCH_EVENT_TRUST.lower(), (
        "CYPHER_BATCH_EVENT_TRUST must use coalesce(k.distorted_summary, best_event.summary) "
        "so that first-hand witnesses (no distorted_summary on their edge) still get "
        "canonical text rather than null."
    )


# ---------------------------------------------------------------------------
# Behavioural test — two-hop propagation scenario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_hop_reader_sees_distorted_not_canonical() -> None:
    """select_batch_event_trust returns hop-distorted text, not canonical Event.summary.

    npc_a witnesses an event (canonical text). npc_b hears from npc_a and receives a
    hop-1 distorted summary on their KNOWS_ABOUT edge. npc_b then tells npc_c; the
    KNOWS_ABOUT edge written for npc_c carries the hop-2 distorted summary. When the
    engine reads pairs [(npc_b, npc_c)], the result must carry the hop-2 distorted
    text, not the canonical Event.summary.

    The fake session routes on whether the query contains ``k.distorted_summary``:
    broken query → canonical text (test fails); fixed query → distorted text (passes).
    Finding CR-L01-01.
    """
    pairs = [{"sharer_id": "npc_b", "receiver_id": "npc_c"}]
    result = await select_batch_event_trust(
        _QueryAwareSession(),  # type: ignore[arg-type]
        pairs=pairs,
    )

    assert len(result) == 1
    assert result[0]["summary"] != _CANONICAL_SUMMARY, (
        "The returned summary is identical to the canonical Event.summary — distortion "
        "from the KNOWS_ABOUT edge is being discarded on read. CR-L01-01."
    )
    assert result[0]["summary"] == _HOP2_DISTORTED, (
        f"Expected hop-2 distorted summary '{_HOP2_DISTORTED}', "
        f"got '{result[0]['summary']}'. CR-L01-01."
    )
