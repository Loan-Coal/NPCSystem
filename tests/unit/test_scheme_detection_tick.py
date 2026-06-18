"""Unit tests for SchemeDetectionTick (F1.6 detection-half / DEC-107).

Verifies the tick self-gates on its interval, marks each discoverable scheme, and
counts only the schemes that actually transitioned active→discovered.

Uses a mock SchemingGraphPort (DEC-122 / SEV-24 Wave 5) — no monkeypatching.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick


def _settings(interval: int = 7, min_steps: int = 2) -> Any:
    return SimpleNamespace(
        SCHEME_DETECTION_TICK_INTERVAL=interval,
        SCHEME_DISCOVERY_MIN_STEPS=min_steps,
    )


def _mock_repo(discoverable: list[str], mark_results: dict[str, bool] | None = None) -> Any:
    """Return a mock SchemingGraphPort with pre-configured responses."""
    results = mark_results or {}
    repo = SimpleNamespace(
        get_discoverable_scheme_ids=AsyncMock(return_value=discoverable),
        mark_scheme_discovered=AsyncMock(side_effect=lambda scheme_id: results.get(scheme_id, True)),
    )
    return repo


@pytest.mark.asyncio
async def test_skips_off_interval_tick() -> None:
    repo = _mock_repo(["s1"])
    adapter = SchemeDetectionTick(settings=_settings(interval=7), scheming_repo=repo)

    result = await adapter.run_tick(tick_id=8)

    assert result == {"tick_id": 8, "discovered": 0, "skipped": True}
    repo.get_discoverable_scheme_ids.assert_not_called()


@pytest.mark.asyncio
async def test_discovers_all_eligible_on_interval() -> None:
    repo = _mock_repo(["s1", "s2"])
    adapter = SchemeDetectionTick(settings=_settings(interval=7), scheming_repo=repo)

    result = await adapter.run_tick(tick_id=14)

    assert result["discovered"] == 2
    assert result["skipped"] is False
    repo.get_discoverable_scheme_ids.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_counts_only_actual_transitions() -> None:
    # s2 already discovered by a race → mark returns False; not counted.
    repo = _mock_repo(["s1", "s2"], {"s2": False})
    adapter = SchemeDetectionTick(settings=_settings(interval=1), scheming_repo=repo)

    result = await adapter.run_tick(tick_id=1)

    assert result["discovered"] == 1


@pytest.mark.asyncio
async def test_no_discoverable_schemes_returns_zero() -> None:
    repo = _mock_repo([])
    adapter = SchemeDetectionTick(settings=_settings(interval=1), scheming_repo=repo)

    result = await adapter.run_tick(tick_id=1)

    assert result["discovered"] == 0
    assert result["skipped"] is False
