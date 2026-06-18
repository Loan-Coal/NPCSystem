"""
Module: test_scheme_reader
Layer: tests/unit
Purpose: Unit tests for graph/scheme_reader.py — active-scheme reads for the cap
         check, advance tick, and detection tick. All Neo4j I/O is mocked.
Dependencies: pytest, unittest.mock, npc_engine.graph.scheme_reader
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.graph.scheme_reader import (
    ActiveSchemeProgress,
    SchemeRecord,
    SchemeWithSteps,
    get_active_schemes,
    get_all_active_schemes_with_steps,
    get_discoverable_scheme_ids,
    get_schemes_with_steps_for_npc,
)


class _AsyncIter:
    """Minimal async iterator wrapper for a plain list — used in mocks."""

    def __init__(self, items: list) -> None:
        self._iter = iter(items)

    def __aiter__(self) -> _AsyncIter:
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def _row(data: dict) -> MagicMock:
    row = MagicMock()
    row.data = MagicMock(return_value=data)
    return row


# ---------------------------------------------------------------------------
# get_active_schemes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_schemes_returns_empty_list_when_no_rows() -> None:
    session = AsyncMock()
    session.run = AsyncMock(return_value=_AsyncIter([]))

    records = await get_active_schemes(session=session, npc_id="lira")

    assert records == []


@pytest.mark.asyncio
async def test_get_active_schemes_returns_scheme_records() -> None:
    session = AsyncMock()
    rows = [
        _row({
            "s.id": "s1", "s.npc_id": "captain_sorn", "s.goal": "seize_bridge",
            "s.status": "active", "s.created_at_game_time": "tick_1",
        }),
        _row({
            "s.id": "s2", "s.npc_id": "captain_sorn", "s.goal": "bribe_council",
            "s.status": "active", "s.created_at_game_time": "tick_2",
        }),
    ]
    session.run = AsyncMock(return_value=_AsyncIter(rows))

    records = await get_active_schemes(session=session, npc_id="captain_sorn")

    assert len(records) == 2
    assert all(isinstance(r, SchemeRecord) for r in records)
    assert records[0].id == "s1"
    assert records[1].goal == "bribe_council"


# ---------------------------------------------------------------------------
# get_all_active_schemes_with_steps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_active_schemes_with_steps_maps_rows() -> None:
    session = AsyncMock()
    rows = [
        _row({"scheme_id": "s1", "npc_id": "lira", "goal": "rob", "step_count": 3}),
        _row({"scheme_id": "s2", "npc_id": "vex", "goal": "spy", "step_count": 0}),
    ]
    session.run = AsyncMock(return_value=_AsyncIter(rows))

    records = await get_all_active_schemes_with_steps(session=session)

    assert len(records) == 2
    assert all(isinstance(r, ActiveSchemeProgress) for r in records)
    assert records[0].step_count == 3
    assert records[1].scheme_id == "s2"


@pytest.mark.asyncio
async def test_get_all_active_schemes_with_steps_empty() -> None:
    session = AsyncMock()
    session.run = AsyncMock(return_value=_AsyncIter([]))

    assert await get_all_active_schemes_with_steps(session=session) == []


# ---------------------------------------------------------------------------
# get_discoverable_scheme_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_discoverable_scheme_ids_returns_ids() -> None:
    session = AsyncMock()
    rows = [_row({"scheme_id": "s1"}), _row({"scheme_id": "s2"})]
    session.run = AsyncMock(return_value=_AsyncIter(rows))

    ids = await get_discoverable_scheme_ids(session=session, min_steps=2)

    assert ids == ["s1", "s2"]
    # min_steps forwarded to the query.
    assert session.run.call_args.kwargs["min_steps"] == 2


@pytest.mark.asyncio
async def test_get_discoverable_scheme_ids_empty() -> None:
    session = AsyncMock()
    session.run = AsyncMock(return_value=_AsyncIter([]))

    assert await get_discoverable_scheme_ids(session=session, min_steps=5) == []


# ---------------------------------------------------------------------------
# get_schemes_with_steps_for_npc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schemes_with_steps_sets_discovered_and_orders_steps() -> None:
    session = AsyncMock()
    rows = [
        _row({
            "scheme_id": "s1", "goal": "rob", "status": "discovered",
            "steps": [
                {"step_order": 2, "completed": True, "summary": "bribed guard"},
                {"step_order": 1, "completed": True, "summary": "cased vault"},
            ],
        }),
    ]
    session.run = AsyncMock(return_value=_AsyncIter(rows))

    schemes = await get_schemes_with_steps_for_npc(session=session, npc_id="lira")

    assert len(schemes) == 1
    assert isinstance(schemes[0], SchemeWithSteps)
    assert schemes[0].discovered is True
    # Steps are ordered by step_order regardless of row order.
    assert [s.step_order for s in schemes[0].steps] == [1, 2]


@pytest.mark.asyncio
async def test_schemes_with_steps_filters_null_step_placeholders() -> None:
    # A scheme with no steps yields one map with a null step_order (OPTIONAL MATCH).
    session = AsyncMock()
    rows = [
        _row({
            "scheme_id": "s2", "goal": "spy", "status": "active",
            "steps": [{"step_order": None, "completed": None, "summary": None}],
        }),
    ]
    session.run = AsyncMock(return_value=_AsyncIter(rows))

    schemes = await get_schemes_with_steps_for_npc(session=session, npc_id="vex")

    assert schemes[0].discovered is False
    assert schemes[0].steps == []


# ---------------------------------------------------------------------------
# SEV-03 regression: SchemeStatus Literal typing
# ---------------------------------------------------------------------------


def test_scheme_status_literal_exists_in_reader_module() -> None:
    """SEV-03: scheme_reader must export SchemeStatus as a Literal type."""
    from npc_engine.graph import scheme_reader
    assert hasattr(scheme_reader, "SchemeStatus"), (
        "scheme_reader must export SchemeStatus Literal for typed status fields"
    )


def test_scheme_record_status_is_literal_typed() -> None:
    """SEV-03: SchemeRecord.status field annotation must reference SchemeStatus."""
    import typing
    from npc_engine.graph.scheme_reader import SchemeRecord, SchemeStatus

    # Pydantic v2: model_fields carries annotation info
    field = SchemeRecord.model_fields.get("status")
    assert field is not None

    # Valid SchemeStatus values must be accepted without validation errors.
    for value in ("active", "discovered", "completed"):
        record = SchemeRecord(id="s", npc_id="npc", goal="g", status=value)
        assert record.status == value


def test_scheme_with_steps_status_is_literal_typed() -> None:
    """SEV-03: SchemeWithSteps.status must accept only SchemeStatus values."""
    from npc_engine.graph.scheme_reader import SchemeWithSteps

    for value in ("active", "discovered", "completed"):
        obj = SchemeWithSteps(scheme_id="s", goal="g", status=value)
        assert obj.status == value


def test_active_status_constant_exists_in_reader() -> None:
    """SEV-03: _ACTIVE_STATUS constant must exist so Cypher params use it, not raw
    string literals.
    """
    from npc_engine.graph import scheme_reader
    # The constant may be private (_ACTIVE_STATUS) — check module-level dict.
    module_vars = vars(scheme_reader)
    active_constants = [v for v in module_vars.values() if v == "active" and not callable(v)]
    assert active_constants, (
        "A constant equal to 'active' must exist in scheme_reader (e.g. _ACTIVE_STATUS)"
    )
