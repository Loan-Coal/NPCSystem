"""Unit tests for the SchemeAdvanceTick scheduler adapter (F1.6 / DEC-107 Option A).

Verifies the tick self-gates on its interval, advances eligible active schemes by
minting a covert Event + SCHEME_STEP, respects the step cap and per-tick cap, and
skips schemes whose owner has no resolvable location.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from npc_engine.engines.scheming import scheme_advance_tick as mod
from npc_engine.engines.scheming.scheme_advance_tick import SchemeAdvanceTick
from npc_engine.graph.scheme_reader import ActiveSchemeProgress


def _settings(interval: int = 5, max_steps: int = 5, max_per_tick: int = 10) -> Any:
    return SimpleNamespace(
        SCHEME_ADVANCE_TICK_INTERVAL=interval,
        MAX_SCHEME_STEPS=max_steps,
        SCHEME_ADVANCE_MAX_PER_TICK=max_per_tick,
    )


def _registry() -> Any:
    # node_models["event"] just echoes kwargs; validate_node_write is mocked to identity.
    return SimpleNamespace(node_models={"event": lambda **kw: kw})


class _Recorder:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []
        self.emitted: list[dict[str, Any]] = []
        self.locations: dict[str, str | None] = {}


def _patch(monkeypatch, recorder: _Recorder, schemes: list[ActiveSchemeProgress]) -> None:
    async def _get_all(session: Any) -> list[ActiveSchemeProgress]:
        return schemes

    async def _get_loc(session: Any, npc_id: str) -> str | None:
        return recorder.locations.get(npc_id, "tavern")

    async def _run_in_tx(session: Any, fn: Any) -> None:
        # Capture the validated event by invoking the emit closure with a fake tx
        # that records the upsert. We instead capture via validate_node_write below.
        await fn(_FakeTx(recorder))

    async def _add_step(*, session: Any, scheme_id: str, event_id: str,
                        step_order: int, completed: bool) -> None:
        recorder.steps.append({
            "scheme_id": scheme_id, "event_id": event_id,
            "step_order": step_order, "completed": completed,
        })

    def _validate(registry: Any, node_type: str, props: dict[str, Any]) -> dict[str, Any]:
        recorder.emitted.append(props)
        return props

    monkeypatch.setattr(mod, "get_all_active_schemes_with_steps", _get_all)
    monkeypatch.setattr(mod, "get_npc_location_id", _get_loc)
    monkeypatch.setattr(mod, "run_in_tx", _run_in_tx)
    monkeypatch.setattr(mod, "add_scheme_step", _add_step)
    monkeypatch.setattr(mod, "validate_node_write", _validate)
    monkeypatch.setattr(mod, "upsert_event", _noop_upsert)


async def _noop_upsert(*, tx: Any, event: Any) -> None:
    return None


class _FakeTx:
    def __init__(self, recorder: _Recorder) -> None:
        self._recorder = recorder


def _scheme(scheme_id: str, npc_id: str, step_count: int) -> ActiveSchemeProgress:
    return ActiveSchemeProgress(
        scheme_id=scheme_id, npc_id=npc_id, goal="rob the vault", step_count=step_count
    )


@pytest.mark.asyncio
async def test_skips_off_interval_tick(monkeypatch) -> None:
    rec = _Recorder()
    _patch(monkeypatch, rec, [_scheme("s1", "lira", 0)])
    adapter = SchemeAdvanceTick(settings=_settings(interval=5), registry=_registry())

    result = await adapter.run_tick(session=object(), tick_id=7)

    assert result == {"tick_id": 7, "advanced": 0, "skipped": True}
    assert rec.steps == []


@pytest.mark.asyncio
async def test_advances_eligible_scheme_on_interval(monkeypatch) -> None:
    rec = _Recorder()
    _patch(monkeypatch, rec, [_scheme("s1", "lira", 2)])
    adapter = SchemeAdvanceTick(settings=_settings(interval=5), registry=_registry())

    result = await adapter.run_tick(session=object(), tick_id=10)

    assert result["advanced"] == 1
    assert result["skipped"] is False
    # Next step_order is step_count + 1.
    assert rec.steps[0]["step_order"] == 3
    assert rec.steps[0]["scheme_id"] == "s1"


@pytest.mark.asyncio
async def test_covert_event_is_private_and_dedicated_type(monkeypatch) -> None:
    rec = _Recorder()
    _patch(monkeypatch, rec, [_scheme("s1", "lira", 0)])
    adapter = SchemeAdvanceTick(settings=_settings(interval=1), registry=_registry())

    await adapter.run_tick(session=object(), tick_id=1)

    props = rec.emitted[0]
    assert props["is_public"] is False
    assert props["event_type"] == "scheme_advance"
    assert props["location_id"] == "tavern"


@pytest.mark.asyncio
async def test_scheme_at_step_cap_is_not_advanced(monkeypatch) -> None:
    rec = _Recorder()
    _patch(monkeypatch, rec, [_scheme("s1", "lira", 5)])
    adapter = SchemeAdvanceTick(settings=_settings(interval=1, max_steps=5), registry=_registry())

    result = await adapter.run_tick(session=object(), tick_id=1)

    assert result["advanced"] == 0
    assert rec.steps == []


@pytest.mark.asyncio
async def test_scheme_without_location_is_skipped(monkeypatch) -> None:
    rec = _Recorder()
    rec.locations["ghost"] = None
    _patch(monkeypatch, rec, [_scheme("s1", "ghost", 0)])
    adapter = SchemeAdvanceTick(settings=_settings(interval=1), registry=_registry())

    result = await adapter.run_tick(session=object(), tick_id=1)

    assert result["advanced"] == 0
    assert rec.steps == []


@pytest.mark.asyncio
async def test_per_tick_cap_limits_advances(monkeypatch) -> None:
    rec = _Recorder()
    schemes = [_scheme(f"s{i}", f"npc{i}", 0) for i in range(5)]
    _patch(monkeypatch, rec, schemes)
    adapter = SchemeAdvanceTick(
        settings=_settings(interval=1, max_per_tick=2), registry=_registry()
    )

    result = await adapter.run_tick(session=object(), tick_id=1)

    assert result["advanced"] == 2
    assert len(rec.steps) == 2
