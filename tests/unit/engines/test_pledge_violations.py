"""
Tests for oath violation detection — S2.3.

Covers check_pledge_violations() in pledge_service, the query helpers in pledge_queries,
and the oath_engine.run_tick wiring (all active pledgers, not just expiring ones).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.political.pledge_violation_service import check_pledge_violations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pledge(pledge_type: str = "fealty", sworn_at_tick: int = 5) -> dict:
    return {
        "pledgee_id": "lord-1",
        "pledge_type": pledge_type,
        "sworn_at_tick": sworn_at_tick,
        "severity": 70,
    }


# ---------------------------------------------------------------------------
# check_pledge_violations — witness-based detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_violation_detected_via_witnessed_edge() -> None:
    """Pledger seen deserting after oath → pledge returned, break_pledge called."""
    session = AsyncMock()

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=[_pledge("fealty", sworn_at_tick=5)],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_witnessed_violations",
            new_callable=AsyncMock,
            return_value=[{"action_type": "desert", "witnessed_at_tick": 10, "event_id": "evt-1"}],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_participated_violations",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.break_pledge",
            new_callable=AsyncMock,
        ) as mock_break,
        patch(
            "npc_engine.graph.political.pledge_violation_service._emit_violation_event",
            new_callable=AsyncMock,
        ) as mock_emit,
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert len(result) == 1
    assert result[0]["pledge_type"] == "fealty"
    mock_break.assert_awaited_once()
    mock_emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_violation_detected_via_participated_in_edge() -> None:
    """Pledger participated as 'rebel' after oath → pledge returned."""
    session = AsyncMock()

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=[_pledge("fealty", sworn_at_tick=5)],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_witnessed_violations",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_participated_violations",
            new_callable=AsyncMock,
            return_value=[{"role": "rebel", "event_id": "evt-2", "tick_id": 12}],
        ),
        patch("npc_engine.graph.political.pledge_violation_service.break_pledge", new_callable=AsyncMock),
        patch("npc_engine.graph.political.pledge_violation_service._emit_violation_event", new_callable=AsyncMock),
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert len(result) == 1
    assert result[0]["pledge_type"] == "fealty"


@pytest.mark.asyncio
async def test_no_violation_when_no_active_pledges() -> None:
    """No active pledges → empty list, no break_pledge called."""
    session = AsyncMock()

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.break_pledge",
            new_callable=AsyncMock,
        ) as mock_break,
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert result == []
    mock_break.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_violation_when_action_type_not_in_violation_set() -> None:
    """WITNESSED edge with a non-violating action type → no violation."""
    session = AsyncMock()

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=[_pledge("fealty", sworn_at_tick=5)],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_witnessed_violations",
            new_callable=AsyncMock,
            return_value=[],  # query filters — empty means no match
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_participated_violations",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.break_pledge",
            new_callable=AsyncMock,
        ) as mock_break,
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert result == []
    mock_break.assert_not_awaited()


@pytest.mark.asyncio
async def test_multiple_pledges_only_violated_ones_returned() -> None:
    """Two active pledges; only one has a violation → only that one returned."""
    session = AsyncMock()

    pledges = [
        _pledge("fealty", sworn_at_tick=5),
        _pledge("protect", sworn_at_tick=3),
    ]

    # fealty has a witnessed violation; protect has none
    def witnessed_side_effect(session, *, pledger_id, since_tick, action_types):
        if "desert" in action_types:
            return [{"action_type": "desert", "witnessed_at_tick": 10, "event_id": "e1"}]
        return []

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=pledges,
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_witnessed_violations",
            side_effect=witnessed_side_effect,
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_participated_violations",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("npc_engine.graph.political.pledge_violation_service.break_pledge", new_callable=AsyncMock),
        patch("npc_engine.graph.political.pledge_violation_service._emit_violation_event", new_callable=AsyncMock),
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert len(result) == 1
    assert result[0]["pledge_type"] == "fealty"


@pytest.mark.asyncio
async def test_same_pledge_not_broken_twice_if_both_checks_trigger() -> None:
    """Both WITNESSED and PARTICIPATED_IN fire for same pledge → break_pledge called once."""
    session = AsyncMock()

    with (
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_active_pledges_for_pledger",
            new_callable=AsyncMock,
            return_value=[_pledge("fealty")],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_witnessed_violations",
            new_callable=AsyncMock,
            return_value=[{"action_type": "desert", "witnessed_at_tick": 10, "event_id": "e1"}],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.get_participated_violations",
            new_callable=AsyncMock,
            return_value=[{"role": "rebel", "event_id": "e2", "tick_id": 11}],
        ),
        patch(
            "npc_engine.graph.political.pledge_violation_service.break_pledge",
            new_callable=AsyncMock,
        ) as mock_break,
        patch("npc_engine.graph.political.pledge_violation_service._emit_violation_event", new_callable=AsyncMock),
    ):
        result = await check_pledge_violations(session, pledger_id="char-1", tick=15)

    assert len(result) == 1
    mock_break.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_active_pledges_for_pledger — query function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_pledges_for_pledger_queries_session() -> None:
    """get_active_pledges_for_pledger runs the right query and returns dicts."""
    from npc_engine.graph.political.pledge_queries import get_active_pledges_for_pledger

    record = MagicMock()
    record.__iter__ = MagicMock(return_value=iter([
        ("pledgee_id", "lord-1"),
        ("pledge_type", "fealty"),
        ("sworn_at_tick", 5),
        ("severity", 70),
    ]))
    record.keys.return_value = ["pledgee_id", "pledge_type", "sworn_at_tick", "severity"]

    result_obj = AsyncMock()
    result_obj.__aiter__ = MagicMock(return_value=_async_iter([record]))
    result_obj.consume = AsyncMock()

    session = AsyncMock()
    session.run.return_value = result_obj

    rows = await get_active_pledges_for_pledger(session, pledger_id="char-1")
    session.run.assert_called_once()
    call_args = session.run.call_args
    assert "char-1" in str(call_args)


# ---------------------------------------------------------------------------
# get_all_active_pledgers — query function
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_active_pledgers_returns_distinct_ids() -> None:
    """get_all_active_pledgers returns a list of distinct pledger IDs."""
    from npc_engine.graph.political.pledge_queries import get_all_active_pledgers

    record = MagicMock()
    record.__getitem__ = MagicMock(side_effect=lambda k: "char-1" if k == "pledger_id" else None)

    result_obj = AsyncMock()
    result_obj.__aiter__ = MagicMock(return_value=_async_iter([record]))
    result_obj.consume = AsyncMock()

    session = AsyncMock()
    session.run.return_value = result_obj

    ids = await get_all_active_pledgers(session)
    assert ids == ["char-1"]
    session.run.assert_called_once()


# ---------------------------------------------------------------------------
# OathEngine.run_tick — checks ALL active pledgers
# ---------------------------------------------------------------------------


def _make_pledge_repo(
    expiring: list[dict] | None = None,
    pledgers: list[str] | None = None,
    violations: list[dict] | None = None,
) -> AsyncMock:
    """Build a mock PledgeGraphPort for OathEngine."""
    repo = AsyncMock()
    repo.get_expiring_pledges = AsyncMock(return_value=expiring or [])
    repo.break_pledge = AsyncMock()
    repo.get_all_active_pledgers = AsyncMock(return_value=pledgers or [])
    repo.check_pledge_violations = AsyncMock(return_value=violations or [])
    return repo


@pytest.mark.asyncio
async def test_oath_engine_checks_all_active_pledgers() -> None:
    """run_tick calls check_pledge_violations for each active pledger, not just expiring ones."""
    from npc_engine.engines.oath.oath_engine import OathEngine

    repo = _make_pledge_repo(expiring=[], pledgers=["char-1", "char-2"], violations=[])
    engine = OathEngine(pledge_repo=repo)

    result = await engine.run_tick(tick_id=20)

    assert repo.check_pledge_violations.await_count == 2
    checked_ids = {c.kwargs["pledger_id"] for c in repo.check_pledge_violations.await_args_list}
    assert checked_ids == {"char-1", "char-2"}
    assert result["expired_pledges"] == 0


@pytest.mark.asyncio
async def test_oath_engine_includes_violation_count_in_result() -> None:
    """run_tick result dict includes violated_pledges count."""
    from npc_engine.engines.oath.oath_engine import OathEngine

    repo = _make_pledge_repo(
        expiring=[], pledgers=["char-1"], violations=[{"pledge_type": "fealty"}]
    )
    engine = OathEngine(pledge_repo=repo)

    result = await engine.run_tick(tick_id=20)

    assert result["violated_pledges"] == 1


# ---------------------------------------------------------------------------
# Helper for async iteration in tests
# ---------------------------------------------------------------------------

class _async_iter:
    def __init__(self, items):
        self._items = list(items)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item
