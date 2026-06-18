"""Unit tests for the SchemeAdvanceTick scheduler adapter (F1.6 / DEC-107 Option A).

Verifies the tick self-gates on its interval, advances eligible active schemes by
minting a covert Event + SCHEME_STEP, respects the step cap and per-tick cap, and
skips schemes whose owner has no resolvable location. All graph I/O is mocked via
SchemingGraphPort (DEC-122 / SEV-24).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.scheming.scheme_advance_tick import SchemeAdvanceTick
from npc_engine.graph.scheme_reader import ActiveSchemeProgress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(interval: int = 5, max_steps: int = 5, max_per_tick: int = 10) -> Any:
    return SimpleNamespace(
        SCHEME_ADVANCE_TICK_INTERVAL=interval,
        MAX_SCHEME_STEPS=max_steps,
        SCHEME_ADVANCE_MAX_PER_TICK=max_per_tick,
    )


def _registry() -> Any:
    return SimpleNamespace(node_models={"event": lambda **kw: kw})


def _scheme(scheme_id: str, npc_id: str, step_count: int) -> ActiveSchemeProgress:
    return ActiveSchemeProgress(
        scheme_id=scheme_id, npc_id=npc_id, goal="rob the vault", step_count=step_count
    )


def _make_repo(
    schemes: list[ActiveSchemeProgress] | None = None,
    locations: dict[str, str | None] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_all_active_schemes_with_steps.return_value = schemes or []
    locations = locations or {}

    async def _loc(npc_id: str) -> str | None:
        return locations.get(npc_id, "tavern")

    repo.get_npc_location_id.side_effect = _loc
    repo.emit_scheme_step_atomic.return_value = None
    repo.add_scheme_step.return_value = None
    repo.upsert_scheme.return_value = None
    return repo


def _make_adapter(
    schemes: list[ActiveSchemeProgress] | None = None,
    locations: dict[str, str | None] | None = None,
    interval: int = 5,
    max_steps: int = 5,
    max_per_tick: int = 10,
) -> tuple[SchemeAdvanceTick, AsyncMock]:
    repo = _make_repo(schemes, locations)
    with patch(
        "npc_engine.engines.scheming.scheme_advance_tick.validate_node_write",
        side_effect=lambda _reg, _type, props: props,
    ):
        adapter = SchemeAdvanceTick(
            settings=_settings(interval=interval, max_steps=max_steps, max_per_tick=max_per_tick),
            registry=_registry(),
            scheming_repo=repo,
        )
    return adapter, repo


# ---------------------------------------------------------------------------
# Interval gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skips_off_interval_tick() -> None:
    adapter, repo = _make_adapter(schemes=[_scheme("s1", "lira", 0)], interval=5)

    result = await adapter.run_tick(tick_id=7)

    assert result == {"tick_id": 7, "advanced": 0, "skipped": True}
    repo.get_all_active_schemes_with_steps.assert_not_called()


@pytest.mark.asyncio
async def test_advances_eligible_scheme_on_interval() -> None:
    adapter, repo = _make_adapter(schemes=[_scheme("s1", "lira", 2)], interval=5)

    with patch(
        "npc_engine.engines.scheming.scheme_advance_tick.validate_node_write",
        side_effect=lambda _r, _t, p: p,
    ):
        result = await adapter.run_tick(tick_id=10)

    assert result["advanced"] == 1
    assert result["skipped"] is False
    repo.emit_scheme_step_atomic.assert_called_once()
    call_kwargs = repo.emit_scheme_step_atomic.call_args[1]
    assert call_kwargs["scheme_id"] == "s1"
    assert call_kwargs["step_order"] == 3


@pytest.mark.asyncio
async def test_covert_event_is_private_and_dedicated_type() -> None:
    adapter, repo = _make_adapter(schemes=[_scheme("s1", "lira", 0)], interval=1)

    emitted_props: list[dict] = []

    async def _capture_emit(**kwargs: Any) -> None:
        emitted_props.append(kwargs["event"])

    repo.emit_scheme_step_atomic.side_effect = _capture_emit

    with patch(
        "npc_engine.engines.scheming.scheme_advance_tick.validate_node_write",
        side_effect=lambda _r, _t, p: p,
    ):
        await adapter.run_tick(tick_id=1)

    assert emitted_props, "emit_scheme_step_atomic was not called"
    props = emitted_props[0]
    assert props["is_public"] is False
    assert props["event_type"] == "scheme_advance"
    assert props["location_id"] == "tavern"


@pytest.mark.asyncio
async def test_scheme_at_step_cap_is_not_advanced() -> None:
    adapter, repo = _make_adapter(schemes=[_scheme("s1", "lira", 5)], interval=1, max_steps=5)

    result = await adapter.run_tick(tick_id=1)

    assert result["advanced"] == 0
    repo.emit_scheme_step_atomic.assert_not_called()


@pytest.mark.asyncio
async def test_scheme_without_location_is_skipped() -> None:
    adapter, repo = _make_adapter(
        schemes=[_scheme("s1", "ghost", 0)],
        locations={"ghost": None},
        interval=1,
    )

    result = await adapter.run_tick(tick_id=1)

    assert result["advanced"] == 0
    repo.emit_scheme_step_atomic.assert_not_called()


@pytest.mark.asyncio
async def test_per_tick_cap_limits_advances() -> None:
    schemes = [_scheme(f"s{i}", f"npc{i}", 0) for i in range(5)]
    adapter, repo = _make_adapter(schemes=schemes, interval=1, max_per_tick=2)

    with patch(
        "npc_engine.engines.scheming.scheme_advance_tick.validate_node_write",
        side_effect=lambda _r, _t, p: p,
    ):
        result = await adapter.run_tick(tick_id=1)

    assert result["advanced"] == 2
    assert repo.emit_scheme_step_atomic.call_count == 2


# ---------------------------------------------------------------------------
# SEV-01 atomicity regression: Event mint + SCHEME_STEP must be in ONE call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_and_step_share_single_atomic_call() -> None:
    """SEV-01: emit_scheme_step_atomic must be called exactly ONCE per scheme advance.

    The port is responsible for the within-transaction atomicity; the engine
    must not call add_scheme_step separately.
    """
    adapter, repo = _make_adapter(schemes=[_scheme("s1", "lira", 0)], interval=1)

    with patch(
        "npc_engine.engines.scheming.scheme_advance_tick.validate_node_write",
        side_effect=lambda _r, _t, p: p,
    ):
        result = await adapter.run_tick(tick_id=1)

    assert result["advanced"] == 1
    assert repo.emit_scheme_step_atomic.call_count == 1, (
        "Expected exactly one emit_scheme_step_atomic call per scheme advance"
    )
    repo.add_scheme_step.assert_not_called()


@pytest.mark.asyncio
async def test_run_tick_no_session_required() -> None:
    """run_tick accepts no session kwarg (DEC-122 Wave 5 — session coupling removed)."""
    adapter, _ = _make_adapter(schemes=[], interval=5)

    result = await adapter.run_tick(tick_id=7)

    assert result["skipped"] is True
