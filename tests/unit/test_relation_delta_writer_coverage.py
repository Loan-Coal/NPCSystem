"""
test_relation_delta_writer_coverage.py - Unit tests for graph.relation_delta_writer.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: mock AsyncSession, mock Settings.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.relation_delta_writer import apply_relation_delta
from npc_engine.utils.errors import RelationDeltaExceededError, RelationEdgeNotFoundError


def _make_settings(
    max_per_turn: int = 15,
    max_per_window: int = 40,
    window_size: int = 10,
) -> MagicMock:
    s = MagicMock()
    s.MAX_RELATION_DELTA_PER_TURN = max_per_turn
    s.MAX_RELATION_DELTA_PER_WINDOW = max_per_window
    s.RELATION_WINDOW_SIZE = window_size
    return s


def _make_delta_log_row(delta_log_json: str) -> MagicMock:
    """Build a row mock for the delta_log Cypher query."""
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda key: delta_log_json if key == "delta_log" else None)
    return row


def _make_session_for_delta_writer(
    current_values: dict,
    delta_log_json: str = "[]",
    edge_missing: bool = False,
) -> AsyncMock:
    """Build a mock session where begin_transaction() returns an async context manager.

    The transaction mock handles:
    1. First tx.run() → delta_log query → returns delta_log_json row (or None if missing_edge)
    2. All further tx.run() → no-op cursors (SET / MATCH)
    """
    dl_cursor = AsyncMock()
    if edge_missing:
        dl_cursor.single = AsyncMock(return_value=None)
    else:
        dl_cursor.single = AsyncMock(return_value=_make_delta_log_row(delta_log_json))

    noop_cursor = AsyncMock()
    noop_cursor.single = AsyncMock(return_value=None)

    call_count = [0]

    async def _tx_run(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return dl_cursor
        return noop_cursor

    tx = AsyncMock()
    tx.run = _tx_run
    tx.commit = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)

    session = AsyncMock()
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


# ---------------------------------------------------------------------------
# Happy-path write
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_relation_delta_happy_path() -> None:
    """Valid delta on existing edge must return clamped new values."""
    current = {"trust": 50, "fear": 10, "affection": 60}
    session = _make_session_for_delta_writer(current_values=current)
    settings = _make_settings()

    with (
        patch("npc_engine.graph.relation_delta_writer.get_relation_values", return_value=current),
        patch("npc_engine.graph.relation_delta_writer.set_relation_values", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.write_delta_log", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.record_graph_write_metrics"),
    ):
        result = await apply_relation_delta(
            session=session,
            settings=settings,
            src_id="npc_a",
            dst_id="npc_b",
            deltas={"trust": 5, "fear": -3, "affection": 0},
            cause_id="ev_001",
            tick_id=42,
        )

    assert result["trust"] == 55
    assert result["fear"] == 7
    assert result["affection"] == 60


# ---------------------------------------------------------------------------
# Edge not found → RelationEdgeNotFoundError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_relation_delta_missing_edge_raises() -> None:
    """When the RELATES_TO edge is absent, must raise RelationEdgeNotFoundError."""
    current = {"trust": 50, "fear": 0, "affection": 50}
    session = _make_session_for_delta_writer(current_values=current, edge_missing=True)
    settings = _make_settings()

    with (
        patch("npc_engine.graph.relation_delta_writer.get_relation_values", return_value=current),
        patch("npc_engine.graph.relation_delta_writer.set_relation_values", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.write_delta_log", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.record_graph_write_metrics"),
    ):
        with pytest.raises(RelationEdgeNotFoundError) as exc_info:
            await apply_relation_delta(
                session=session,
                settings=settings,
                src_id="npc_a",
                dst_id="ghost",
                deltas={"trust": 5},
                cause_id="ev_001",
                tick_id=1,
            )

    assert exc_info.value.src_id == "npc_a"
    assert exc_info.value.dst_id == "ghost"


# ---------------------------------------------------------------------------
# Delta too large → RelationDeltaExceededError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_relation_delta_exceeds_turn_raises() -> None:
    """Delta exceeding max_per_turn must raise RelationDeltaExceededError."""
    current = {"trust": 50, "fear": 0, "affection": 50}
    session = _make_session_for_delta_writer(current_values=current)
    settings = _make_settings(max_per_turn=15)

    with (
        patch("npc_engine.graph.relation_delta_writer.get_relation_values", return_value=current),
        patch("npc_engine.graph.relation_delta_writer.set_relation_values", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.write_delta_log", return_value=None),
        patch("npc_engine.graph.relation_delta_writer.record_graph_write_metrics"),
    ):
        with pytest.raises(RelationDeltaExceededError):
            await apply_relation_delta(
                session=session,
                settings=settings,
                src_id="npc_a",
                dst_id="npc_b",
                deltas={"trust": 99},  # far exceeds max_per_turn=15
                cause_id="ev_001",
                tick_id=1,
            )
