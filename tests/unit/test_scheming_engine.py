"""
Module: test_scheming_engine
Layer: tests/unit
Purpose: Unit tests for engines/scheming/scheming_engine.py — forms a capped
         scheme and advances one step. All graph I/O is mocked via SchemingGraphPort.
Dependencies: pytest, unittest.mock, npc_engine.engines.scheming.scheming_engine
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.scheming.scheming_engine import (
    SchemeInput,
    SchemeStepInput,
    SchemingEngine,
)
from npc_engine.graph.intrigue.scheme_reader import SchemeRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(max_active: int = 2) -> SimpleNamespace:
    return SimpleNamespace(MAX_ACTIVE_SCHEMES_PER_NPC=max_active)


def _make_repo(active_schemes: list[SchemeRecord] | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_schemes.return_value = active_schemes or []
    repo.upsert_scheme.return_value = None
    repo.add_scheme_step.return_value = None
    return repo


def _make_engine(max_active: int = 2, active_schemes: list[SchemeRecord] | None = None) -> tuple[SchemingEngine, AsyncMock]:
    repo = _make_repo(active_schemes)
    engine = SchemingEngine(settings=_make_settings(max_active), scheming_repo=repo)
    return engine, repo


# ---------------------------------------------------------------------------
# form_scheme
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_form_scheme_persists_node_and_edge() -> None:
    """form_scheme calls upsert_scheme when NPC is below the cap."""
    engine, repo = _make_engine(max_active=2)

    result = await engine.form_scheme(
        SchemeInput(npc_id="aldric", goal="corner_grain_market", tick=1)
    )

    repo.upsert_scheme.assert_called_once()
    assert result is not None
    assert result.npc_id == "aldric"
    assert result.goal == "corner_grain_market"


@pytest.mark.asyncio
async def test_cap_blocks_excess_schemes() -> None:
    """form_scheme returns None (capped) when NPC already has MAX active schemes."""
    existing = [
        SchemeRecord(id=f"s{i}", npc_id="aldric", goal=f"goal_{i}", status="active")
        for i in range(2)
    ]
    engine, repo = _make_engine(max_active=2, active_schemes=existing)

    result = await engine.form_scheme(
        SchemeInput(npc_id="aldric", goal="third_scheme", tick=5)
    )

    repo.upsert_scheme.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# advance_step
# ---------------------------------------------------------------------------


def _make_registry() -> MagicMock:
    """Return a mock TypeRegistry that validates props unchanged and returns a mock model."""
    from unittest.mock import MagicMock
    registry = MagicMock()
    registry.node_models = {"event": MagicMock(return_value=MagicMock())}
    # validate_node_write passes props through unchanged in the mock
    return registry


def _make_engine_with_registry(
    max_active: int = 2,
    active_schemes: list[SchemeRecord] | None = None,
) -> tuple[SchemingEngine, AsyncMock, MagicMock]:
    """Make engine with TypeRegistry injected (ISSUE-108 path)."""
    from npc_engine.type_registry.node_validator import validate_node_write
    repo = _make_repo(active_schemes)
    repo.get_npc_location_id = AsyncMock(return_value="loc_tavern")
    repo.emit_scheme_step_atomic = AsyncMock()
    registry = _make_registry()
    engine = SchemingEngine(
        settings=_make_settings(max_active),
        scheming_repo=repo,
        registry=registry,
    )
    return engine, repo, registry


@pytest.mark.asyncio
async def test_advance_step_uses_emit_scheme_step_atomic_when_registry_injected() -> None:
    """ISSUE-108: advance_step calls emit_scheme_step_atomic (not add_scheme_step) when
    TypeRegistry is injected, ensuring Event + SCHEME_STEP are written atomically."""
    engine, repo, _registry = _make_engine_with_registry()

    await engine.advance_step(
        SchemeStepInput(
            scheme_id="s1", npc_id="aldric", goal="corner_grain",
            location_id="loc_market", step_order=1, completed=False
        )
    )

    repo.emit_scheme_step_atomic.assert_awaited_once()
    kwargs = repo.emit_scheme_step_atomic.call_args.kwargs
    assert kwargs["scheme_id"] == "s1"
    assert kwargs["step_order"] == 1
    assert kwargs["completed"] is False
    repo.add_scheme_step.assert_not_called()


@pytest.mark.asyncio
async def test_advance_step_marks_completed() -> None:
    """advance_step forwards completed=True via emit_scheme_step_atomic."""
    engine, repo, _ = _make_engine_with_registry()

    await engine.advance_step(
        SchemeStepInput(
            scheme_id="s2", npc_id="aldric", goal="corner_grain",
            location_id="loc_market", step_order=3, completed=True
        )
    )

    kwargs = repo.emit_scheme_step_atomic.call_args.kwargs
    assert kwargs["completed"] is True
