"""
test_graph_rag_queries.py - Unit tests for graph.graph_rag_queries seed expansion.

Does NOT: touch Neo4j (asserts query composition + passes a mock session).

ISSUE-056 (S22.1): the seed MATCH must carry a node-label filter so GraphRAG
expansion never triggers a full-node scan and never anchors on unintended types.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.graph import graph_rag_queries
from npc_engine.graph.graph_rag_queries import _CYPHER_EXPAND_SEEDS, expand_seeds
from npc_engine.graph.infra.labels import EVENT


def test_seed_match_is_label_filtered_not_full_scan() -> None:
    """Seed match must restrict to the Event label, not bare `MATCH (seed)`."""
    assert f":{EVENT}" in _CYPHER_EXPAND_SEEDS
    assert "MATCH (seed)\n" not in _CYPHER_EXPAND_SEEDS
    assert "MATCH (seed) " not in _CYPHER_EXPAND_SEEDS


@pytest.mark.asyncio
async def test_expand_seeds_passes_params_through() -> None:
    """expand_seeds forwards seed_ids/edge_types to the session and returns rows."""
    result_obj = AsyncMock()
    result_obj.data = AsyncMock(return_value=[{"seed_id": "ev_1", "neighbor_id": "ev_2"}])
    session = AsyncMock()
    session.run = AsyncMock(return_value=result_obj)

    rows = await expand_seeds(session, seed_ids=["ev_1"], edge_types=["KNOWS_ABOUT"])

    assert rows == [{"seed_id": "ev_1", "neighbor_id": "ev_2"}]
    session.run.assert_awaited_once_with(
        graph_rag_queries._CYPHER_EXPAND_SEEDS,
        seed_ids=["ev_1"],
        edge_types=["KNOWS_ABOUT"],
    )
