"""Unit tests for SchemeDetectionTick (F1.6 detection-half / DEC-107).

Verifies the tick self-gates on its interval, marks each discoverable scheme, and
counts only the schemes that actually transitioned active→discovered.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from npc_engine.engines.investigation import scheme_detection_tick as mod
from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick


def _settings(interval: int = 7, min_steps: int = 2) -> Any:
    return SimpleNamespace(
        SCHEME_DETECTION_TICK_INTERVAL=interval,
        SCHEME_DISCOVERY_MIN_STEPS=min_steps,
    )


def _patch(monkeypatch, discoverable: list[str], mark_results: dict[str, bool]) -> list[str]:
    marked: list[str] = []

    async def _get_ids(session: Any, min_steps: int) -> list[str]:
        return discoverable

    async def _mark(session: Any, scheme_id: str) -> bool:
        marked.append(scheme_id)
        return mark_results.get(scheme_id, True)

    monkeypatch.setattr(mod, "get_discoverable_scheme_ids", _get_ids)
    monkeypatch.setattr(mod, "mark_scheme_discovered", _mark)
    return marked


@pytest.mark.asyncio
async def test_skips_off_interval_tick(monkeypatch) -> None:
    marked = _patch(monkeypatch, ["s1"], {})
    adapter = SchemeDetectionTick(settings=_settings(interval=7))

    result = await adapter.run_tick(session=object(), tick_id=8)

    assert result == {"tick_id": 8, "discovered": 0, "skipped": True}
    assert marked == []


@pytest.mark.asyncio
async def test_discovers_all_eligible_on_interval(monkeypatch) -> None:
    marked = _patch(monkeypatch, ["s1", "s2"], {})
    adapter = SchemeDetectionTick(settings=_settings(interval=7))

    result = await adapter.run_tick(session=object(), tick_id=14)

    assert result["discovered"] == 2
    assert result["skipped"] is False
    assert marked == ["s1", "s2"]


@pytest.mark.asyncio
async def test_counts_only_actual_transitions(monkeypatch) -> None:
    # s2 already discovered by a race → mark returns False; not counted.
    _patch(monkeypatch, ["s1", "s2"], {"s2": False})
    adapter = SchemeDetectionTick(settings=_settings(interval=1))

    result = await adapter.run_tick(session=object(), tick_id=1)

    assert result["discovered"] == 1


@pytest.mark.asyncio
async def test_no_discoverable_schemes_returns_zero(monkeypatch) -> None:
    _patch(monkeypatch, [], {})
    adapter = SchemeDetectionTick(settings=_settings(interval=1))

    result = await adapter.run_tick(session=object(), tick_id=1)

    assert result["discovered"] == 0
    assert result["skipped"] is False
