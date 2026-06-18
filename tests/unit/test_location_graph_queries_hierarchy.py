"""
test_location_graph_queries_hierarchy.py - Unit tests for EXP-87 hierarchy
additions to graph.location_graph_queries.

Covers:
  - get_ancestors returns ordered list of IDs from parent to root.
  - get_ancestors returns empty list when no parent exists.
  - get_descendants returns flattened list of descendant IDs.
  - get_descendants returns empty list when no children exist.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_session_with_records(records: list[dict]) -> MagicMock:
    """Build an async session that yields the given records from run()."""
    session = AsyncMock()

    async def fake_iter():
        for r in records:
            yield r

    mock_result = MagicMock()
    mock_result.__aiter__ = lambda self: fake_iter()
    mock_result.consume = AsyncMock()
    session.run = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# get_ancestors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ancestors_returns_ordered_ids():
    """get_ancestors should return ancestor IDs from immediate parent to root."""
    records = [
        {"id": "loc_city"},
        {"id": "loc_region"},
        {"id": "loc_world"},
    ]
    session = _make_session_with_records(records)

    from npc_engine.graph.location_graph_queries import get_ancestors

    result = await get_ancestors(session, location_id="loc_tavern")

    assert result == ["loc_city", "loc_region", "loc_world"]
    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_get_ancestors_returns_empty_for_root_node():
    """get_ancestors returns empty list when the node has no PART_OF edges."""
    session = _make_session_with_records([])

    from npc_engine.graph.location_graph_queries import get_ancestors

    result = await get_ancestors(session, location_id="loc_world")

    assert result == []


@pytest.mark.asyncio
async def test_get_ancestors_passes_location_id_to_cypher():
    """get_ancestors must forward location_id as a query parameter."""
    session = _make_session_with_records([])

    from npc_engine.graph.location_graph_queries import get_ancestors

    await get_ancestors(session, location_id="loc_barracks")

    call_kwargs = session.run.call_args[1]
    assert call_kwargs["location_id"] == "loc_barracks"


# ---------------------------------------------------------------------------
# get_descendants
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_descendants_returns_flattened_ids():
    """get_descendants should return all descendant IDs in a flat list."""
    records = [
        {"id": "loc_tavern"},
        {"id": "loc_market_square"},
        {"id": "loc_guard_barracks"},
    ]
    session = _make_session_with_records(records)

    from npc_engine.graph.location_graph_queries import get_descendants

    result = await get_descendants(session, location_id="loc_city")

    assert set(result) == {"loc_tavern", "loc_market_square", "loc_guard_barracks"}
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_descendants_returns_empty_for_leaf_node():
    """get_descendants returns empty list when the node has no PART_OF children."""
    session = _make_session_with_records([])

    from npc_engine.graph.location_graph_queries import get_descendants

    result = await get_descendants(session, location_id="loc_tavern")

    assert result == []


@pytest.mark.asyncio
async def test_get_descendants_passes_location_id_to_cypher():
    """get_descendants must forward location_id as a query parameter."""
    session = _make_session_with_records([])

    from npc_engine.graph.location_graph_queries import get_descendants

    await get_descendants(session, location_id="loc_city")

    call_kwargs = session.run.call_args[1]
    assert call_kwargs["location_id"] == "loc_city"
