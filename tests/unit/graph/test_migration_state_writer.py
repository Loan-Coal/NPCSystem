"""
Module: tests.unit.graph.test_migration_state_writer
Layer: tests
Purpose: Unit tests for the R5.4 applied-state ledger — the Cypher it issues, the
         parameters it binds, and what it reports back.
Dependencies: typing, pytest, npc_engine.graph.infra
Used by: make test (pytest discovery), make check via test-cov

No I/O: the session is a recording double, so these assert the statements the writer
issues rather than their effect on a database. The effect is proven by the integration
test against a real test DB.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.graph.infra.migration_state_models import (
    SCHEMA_MIGRATION_LABEL,
    MigrationRecord,
)
from npc_engine.graph.infra.migration_state_writer import (
    applied_direction,
    ensure_ledger_constraint,
    record_migration,
)


class _FakeResult:
    """A driver result that yields one preset record, or none."""

    def __init__(self, record: dict[str, Any] | None) -> None:
        self._record = record

    async def single(self) -> dict[str, Any] | None:
        return self._record


class _RecordingSession:
    """Captures every statement and parameter set the writer issues."""

    def __init__(self, record: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._record = record

    async def run(self, statement: str, **params: Any) -> _FakeResult:
        self.calls.append((statement, params))
        return _FakeResult(self._record)


def _record(**overrides: Any) -> MigrationRecord:
    """Return a migration record, with any field overridden."""
    fields: dict[str, Any] = {
        "id": "add_social_schema",
        "direction": "up",
        "applied_at_iso": "2026-09-03T12:00:00+00:00",
        "reversible": "full",
        "notes": "",
    }
    fields.update(overrides)
    return MigrationRecord(**fields)


@pytest.mark.asyncio
async def test_ensure_ledger_constraint_is_idempotent_by_construction() -> None:
    session = _RecordingSession()
    await ensure_ledger_constraint(session)  # type: ignore[arg-type]
    statement, _ = session.calls[0]
    assert "IF NOT EXISTS" in statement
    assert SCHEMA_MIGRATION_LABEL in statement


@pytest.mark.asyncio
async def test_record_migration_merges_on_the_migration_id() -> None:
    session = _RecordingSession()
    await record_migration(session, _record())  # type: ignore[arg-type]
    statement, params = session.calls[0]
    assert "MERGE" in statement, "re-recording a migration must not create a second node"
    assert params["id"] == "add_social_schema"
    assert params["direction"] == "up"
    assert params["reversible"] == "full"


@pytest.mark.asyncio
async def test_record_migration_binds_every_model_field() -> None:
    session = _RecordingSession()
    record = _record(direction="down", reversible="partial", notes="constraints only")
    await record_migration(session, record)  # type: ignore[arg-type]
    _, params = session.calls[0]
    assert params == record.model_dump()


@pytest.mark.asyncio
async def test_applied_direction_returns_none_when_never_recorded() -> None:
    session = _RecordingSession(record=None)
    assert await applied_direction(session, "add_social_schema") is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_applied_direction_reports_the_recorded_direction() -> None:
    session = _RecordingSession(record={"direction": "down"})
    assert await applied_direction(session, "add_social_schema") == "down"  # type: ignore[arg-type]


def test_migration_record_rejects_an_unknown_direction() -> None:
    with pytest.raises(ValueError):
        _record(direction="sideways")


def test_migration_record_rejects_an_unknown_reversibility() -> None:
    with pytest.raises(ValueError):
        _record(reversible="maybe")


def test_migration_record_is_frozen() -> None:
    with pytest.raises(ValueError):
        _record().id = "other"  # type: ignore[misc]
