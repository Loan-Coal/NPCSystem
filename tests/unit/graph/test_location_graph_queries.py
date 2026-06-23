"""Unit tests for location_graph_queries — all Neo4j calls mocked."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.location.location_graph_queries import (
    create_connection,
    delete_connection,
    get_connections_for_location,
    get_shortest_path,
)


def _make_session(run_return=None, single_return=None):
    """Build a minimal async session mock."""
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value=single_return)

    async def fake_iter():
        if run_return:
            for item in run_return:
                yield item

    mock_result.__aiter__ = lambda self: fake_iter()

    session = AsyncMock()
    session.run = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# create_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_connection_raises_on_self_loop():
    session = _make_session()
    with pytest.raises(ValueError, match="itself"):
        await create_connection(session, from_id="loc_a", to_id="loc_a", kind="road", travel_cost=2)


@pytest.mark.asyncio
async def test_create_connection_calls_session_run():
    session = _make_session()
    await create_connection(session, from_id="loc_a", to_id="loc_b", kind="road", travel_cost=3)
    session.run.assert_called_once()
    call_kwargs = session.run.call_args[1]
    assert call_kwargs["from_id"] == "loc_a"
    assert call_kwargs["to_id"] == "loc_b"
    assert call_kwargs["kind"] == "road"
    assert call_kwargs["travel_cost"] == 3
    assert call_kwargs["is_open"] is True


@pytest.mark.asyncio
async def test_create_connection_default_is_open_true():
    session = _make_session()
    await create_connection(session, from_id="x", to_id="y", kind="sea", travel_cost=10)
    assert session.run.call_args[1]["is_open"] is True


@pytest.mark.asyncio
async def test_create_connection_custom_is_open():
    session = _make_session()
    await create_connection(session, from_id="x", to_id="y", kind="sea", travel_cost=10, is_open=False)
    assert session.run.call_args[1]["is_open"] is False


# ---------------------------------------------------------------------------
# get_connections_for_location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_connections_returns_list():
    records = [
        {"destination_id": "loc_b", "destination_name": "Village", "kind": "road", "travel_cost": 2, "is_open": True},
        {"destination_id": "loc_c", "destination_name": "Castle", "kind": "river", "travel_cost": 5, "is_open": True},
    ]
    session = _make_session(run_return=records)
    result = await get_connections_for_location(session, location_id="loc_a")
    assert len(result) == 2
    assert result[0]["destination_id"] == "loc_b"
    assert result[1]["kind"] == "river"


@pytest.mark.asyncio
async def test_get_connections_empty():
    session = _make_session(run_return=[])
    result = await get_connections_for_location(session, location_id="loc_isolated")
    assert result == []


# ---------------------------------------------------------------------------
# get_shortest_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shortest_path_same_location_returns_trivial():
    session = _make_session()
    result = await get_shortest_path(session, from_location_id="loc_a", to_location_id="loc_a")
    assert result == {"node_ids": ["loc_a"], "hops": [], "total_cost": 0}
    session.run.assert_not_called()


@pytest.mark.asyncio
async def test_shortest_path_found():
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "node_ids": ["loc_a", "loc_b", "loc_c"],
        "hops": [{"kind": "road", "travel_cost": 2}, {"kind": "road", "travel_cost": 3}],
        "total_cost": 5,
    }[key]
    session = _make_session(single_return=row)
    result = await get_shortest_path(session, from_location_id="loc_a", to_location_id="loc_c")
    assert result["node_ids"] == ["loc_a", "loc_b", "loc_c"]
    assert result["total_cost"] == 5
    assert len(result["hops"]) == 2


@pytest.mark.asyncio
async def test_shortest_path_not_found_returns_none():
    session = _make_session(single_return=None)
    result = await get_shortest_path(session, from_location_id="loc_a", to_location_id="loc_z")
    assert result is None


# ---------------------------------------------------------------------------
# delete_connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_connection_calls_session_run():
    session = _make_session()
    await delete_connection(session, from_id="loc_a", to_id="loc_b")
    session.run.assert_called_once()
    assert session.run.call_args[1]["from_id"] == "loc_a"
    assert session.run.call_args[1]["to_id"] == "loc_b"
