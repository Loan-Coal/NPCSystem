"""Unit tests for TreatyEngine — graph access via a mocked TreatyGraphPort."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.treaty.treaty_engine import TreatyEngine


def _make_repo(
    expiring: list[str] | None = None,
    active: list[str] | None = None,
    violations: list[str] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_expiring_treaties = AsyncMock(return_value=expiring or [])
    repo.expire_treaty = AsyncMock()
    repo.get_all_active_treaty_ids = AsyncMock(return_value=active or [])
    repo.check_treaty_conditions_mechanical = AsyncMock(return_value=violations or [])
    return repo


@pytest.mark.asyncio
async def test_expires_treaties_past_deadline():
    repo = _make_repo(expiring=["t1", "t2"], active=[])
    engine = TreatyEngine(treaty_repo=repo)

    result = await engine.run_tick(tick_id=10)

    assert result["expired_treaties"] == 2
    assert repo.expire_treaty.await_count == 2
    repo.expire_treaty.assert_any_await(treaty_id="t1", tick_id=10)


@pytest.mark.asyncio
async def test_counts_violations_across_active_treaties():
    repo = _make_repo(expiring=[], active=["t1", "t2"], violations=["broke clause A"])
    engine = TreatyEngine(treaty_repo=repo)

    result = await engine.run_tick(tick_id=5)

    # one violation per active treaty (mock returns the same list each call)
    assert result["violations_detected"] == 2
    assert repo.check_treaty_conditions_mechanical.await_count == 2


@pytest.mark.asyncio
async def test_no_treaties_is_noop():
    repo = _make_repo(expiring=[], active=[])
    engine = TreatyEngine(treaty_repo=repo)

    result = await engine.run_tick(tick_id=1)

    assert result == {"expired_treaties": 0, "violations_detected": 0}
    repo.expire_treaty.assert_not_called()


@pytest.mark.asyncio
async def test_run_tick_no_session_required():
    """run_tick accepts no session kwarg (SEV-24 Wave 5 — session coupling removed)."""
    repo = _make_repo(expiring=["t1"], active=[])
    engine = TreatyEngine(treaty_repo=repo)

    result = await engine.run_tick(tick_id=3)

    assert result["expired_treaties"] == 1
