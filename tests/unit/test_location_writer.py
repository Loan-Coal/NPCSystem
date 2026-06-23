"""
test_location_writer.py - Unit tests for graph.location_writer (EXP-87).

Covers:
  - write_part_of calls MERGE Cypher with correct params.
  - write_part_of is idempotent (second call with same params doesn't raise).
  - delete_part_of calls DELETE Cypher with correct params.

Does NOT: connect to Neo4j. All graph calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest


def _make_session() -> MagicMock:
    """Return an AsyncMock behaving like an AsyncSession."""
    session = AsyncMock()
    mock_result = AsyncMock()
    session.run = AsyncMock(return_value=mock_result)
    return session


# ---------------------------------------------------------------------------
# write_part_of
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_part_of_calls_session_run():
    """write_part_of must call session.run exactly once."""
    from npc_engine.graph.location.location_writer import write_part_of

    session = _make_session()
    await write_part_of(session, child_id="loc_tavern", parent_id="loc_city", hierarchy_level=0)

    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_write_part_of_passes_correct_params():
    """write_part_of must forward child_id, parent_id, and hierarchy_level."""
    from npc_engine.graph.location.location_writer import write_part_of

    session = _make_session()
    await write_part_of(session, child_id="loc_tavern", parent_id="loc_city", hierarchy_level=0)

    call_kwargs = session.run.call_args[1]
    assert call_kwargs["child_id"] == "loc_tavern"
    assert call_kwargs["parent_id"] == "loc_city"
    assert call_kwargs["level"] == 0


@pytest.mark.asyncio
async def test_write_part_of_passes_established_at():
    """write_part_of must include an established_at timestamp string."""
    from npc_engine.graph.location.location_writer import write_part_of

    session = _make_session()
    await write_part_of(session, child_id="loc_x", parent_id="loc_y", hierarchy_level=1)

    call_kwargs = session.run.call_args[1]
    assert "now" in call_kwargs
    assert isinstance(call_kwargs["now"], str)
    assert len(call_kwargs["now"]) > 0


@pytest.mark.asyncio
async def test_write_part_of_is_idempotent():
    """Calling write_part_of twice with the same args must not raise."""
    from npc_engine.graph.location.location_writer import write_part_of

    session = _make_session()
    await write_part_of(session, child_id="loc_a", parent_id="loc_b", hierarchy_level=0)
    await write_part_of(session, child_id="loc_a", parent_id="loc_b", hierarchy_level=0)

    assert session.run.call_count == 2


@pytest.mark.asyncio
async def test_write_part_of_raises_on_self_loop():
    """write_part_of must raise ValueError when child_id == parent_id."""
    from npc_engine.graph.location.location_writer import write_part_of

    session = _make_session()
    with pytest.raises(ValueError, match="itself"):
        await write_part_of(session, child_id="loc_a", parent_id="loc_a", hierarchy_level=0)


# ---------------------------------------------------------------------------
# delete_part_of
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_part_of_calls_session_run():
    """delete_part_of must call session.run exactly once."""
    from npc_engine.graph.location.location_writer import delete_part_of

    session = _make_session()
    await delete_part_of(session, child_id="loc_tavern", parent_id="loc_city")

    session.run.assert_called_once()


@pytest.mark.asyncio
async def test_delete_part_of_passes_correct_params():
    """delete_part_of must forward child_id and parent_id."""
    from npc_engine.graph.location.location_writer import delete_part_of

    session = _make_session()
    await delete_part_of(session, child_id="loc_tavern", parent_id="loc_city")

    call_kwargs = session.run.call_args[1]
    assert call_kwargs["child_id"] == "loc_tavern"
    assert call_kwargs["parent_id"] == "loc_city"
