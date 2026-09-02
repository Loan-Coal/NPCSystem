"""
test_graph_outage.py - Integration tests for the Neo4j outage -> 503 contract.

Does NOT: exercise the HTTP layer; the handler mapping is covered by
tests/unit/api/test_graph_outage_503.py.

Dependencies injected: Settings pointed at an unreachable bolt endpoint.
"""

from __future__ import annotations

import pytest

from npc_engine.config import Settings
from npc_engine.graph.infra.db import GraphDB
from npc_engine.utils.errors import GraphUnavailableError


# A port nothing listens on, so the driver fails to connect deterministically.
# Chosen over stopping the neo4j container, which would break every other test
# in this suite for the duration of the run.
_UNREACHABLE_URI = "bolt://localhost:1"
_TEST_API_KEY = "local_dev_secret_change_this_2026"


def _unreachable_graph_db() -> GraphDB:
    """Build a GraphDB whose driver cannot reach any server."""
    settings = Settings(API_KEY_SECRET=_TEST_API_KEY, NEO4J_URI=_UNREACHABLE_URI)
    return GraphDB(settings=settings)


@pytest.mark.asyncio
async def test_unreachable_bolt_raises_graph_unavailable() -> None:
    """A driver outage surfaces as GraphUnavailableError, not a raw neo4j error.

    Nothing in src/ raised GraphUnavailableError before R3.2, while three
    docstrings promised the contract, so the API catch-all answered 500 where the
    Unreal client needs a retryable 503.
    """
    graph_db = _unreachable_graph_db()
    await graph_db.connect()
    try:
        with pytest.raises(GraphUnavailableError) as caught:
            async with graph_db.get_session() as session:
                result = await session.run("RETURN 1 AS n")
                await result.single()
    finally:
        await graph_db.close()

    assert caught.value.uri == _UNREACHABLE_URI
    assert caught.value.cause


@pytest.mark.asyncio
async def test_graph_unavailable_carries_the_configured_uri() -> None:
    """The error records which endpoint failed so operators can act on the log."""
    graph_db = _unreachable_graph_db()
    await graph_db.connect()
    try:
        with pytest.raises(GraphUnavailableError) as caught:
            async with graph_db.get_session() as session:
                await (await session.run("RETURN 1 AS n")).single()
    finally:
        await graph_db.close()

    assert "GraphUnavailableError(" in str(caught.value)
    assert _UNREACHABLE_URI in str(caught.value)
