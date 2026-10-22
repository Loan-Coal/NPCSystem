"""
Module: test_gossip_batch_mispairing
Layer: tests/unit/graph
Purpose: Verifies that CYPHER_BATCH_EVENT_TRUST collects a single map per row
         so that event_id and distorted_summary are always paired from the same row.
         Three separate head(collect(field)) calls mispair when collect() drops nulls —
         the three head() values can come from different events (ISSUE-228).
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

_NULL_SUMMARY_EVENT_ID = "event_canonical"
_DISTORTED_TEXT = "Exaggerated rumour text from a different event"


def test_batch_event_query_collects_single_map_per_row() -> None:
    """CYPHER_BATCH_EVENT_TRUST must use head(collect({...})) to prevent null-drop mispairing.

    Three separate head(collect(field)) calls lose column alignment when some rows
    have null distorted_summary — collect() drops nulls so the three collects can
    have different lengths, making head() return values from different rows (ISSUE-228).
    """
    query_lower = CYPHER_BATCH_EVENT_TRUST.lower()
    # Count bare head(collect(field) patterns — the fixed form uses head(collect({
    # so we strip that form first to avoid false positives.
    bare_count = query_lower.replace("head(collect({", "").count("head(collect(")
    assert bare_count == 0, (
        f"Query has {bare_count} separate head(collect(field)) call(s) — "
        "collect() drops nulls, mispairing event/is_canonical/distorted_summary "
        "when some rows have null distorted_summary (ISSUE-228)."
    )


class _MispairingAwareSession:
    """Fake Neo4j session routing on whether the query uses safe single-map collection.

    Broken query (separate head(collect(field))): returns a canonical event_id but the
    non-null distorted summary — simulating the mispair.
    Fixed query (head(collect({...}))): returns them correctly paired.
    """

    async def run(self, query: str, **_kw: Any) -> Any:
        """Return rows depending on whether the query guards against mispairing."""
        uses_map_collect = "head(collect({" in query
        if uses_map_collect:
            rows: list[dict[str, Any]] = [{
                "sharer_id": "npc_a",
                "receiver_id": "npc_b",
                "event_id": _NULL_SUMMARY_EVENT_ID,
                "summary": "canonical summary text",
                "severity": 90,
                "is_canonical": True,
                "trust": 60,
                "sharer_distortion_level": 0,
            }]
        else:
            rows = [{
                "sharer_id": "npc_a",
                "receiver_id": "npc_b",
                "event_id": _NULL_SUMMARY_EVENT_ID,
                "summary": _DISTORTED_TEXT,
                "severity": 90,
                "is_canonical": True,
                "trust": 60,
            }]

        async def _aiter() -> Any:
            for row in rows:
                yield row

        return _aiter()


@pytest.mark.asyncio
async def test_null_summary_candidate_does_not_mispair_summary() -> None:
    """A canonical event with null distorted_summary must not borrow a summary from another row.

    The canonical event (is_canonical=True) typically has no distorted_summary; a
    non-canonical sibling may have one. With three separate head(collect()) calls,
    collect() drops the canonical event's null so the distorted_summary slot is filled
    from the non-canonical event — mispairing event_id=canonical with distorted text.
    The fixed query uses head(collect({...})) so all fields come from the same row.
    """
    pairs = [{"sharer_id": "npc_a", "receiver_id": "npc_b"}]
    result = await select_batch_event_trust(
        _MispairingAwareSession(),  # type: ignore[arg-type]
        pairs=pairs,
    )

    assert len(result) == 1
    row = result[0]
    assert row["event_id"] == _NULL_SUMMARY_EVENT_ID, (
        f"event_id must be the canonical event; got {row['event_id']!r}"
    )
    assert row["summary"] != _DISTORTED_TEXT, (
        "summary is the distorted text from a different candidate event — "
        "the query is mispairing event_id and distorted_summary (ISSUE-228)."
    )
