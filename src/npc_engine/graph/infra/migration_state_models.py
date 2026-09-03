"""
Module: migration_state_models
Layer: graph
Purpose: The typed record of one schema migration having been applied or reverted.
Does NOT: execute Cypher, open a session, or decide when a migration runs.
Dependencies injected: None (pure data model).
Used by: graph.infra.migration_state_writer, scripts/migrations/*
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Node label carrying the applied-state ledger. Infrastructure, like the constraints in
# schema_bootstrap — deliberately not a type_registry domain node (DEC-254).
SCHEMA_MIGRATION_LABEL = "SchemaMigration"

MigrationDirection = Literal["up", "down"]

# How completely a migration can be undone. "partial" is the honest answer for a
# migration whose backfill wrote a value indistinguishable from an authored one.
Reversibility = Literal["full", "partial", "none"]


class MigrationRecord(BaseModel):
    """One applied-state ledger entry for a single migration run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Migration module stem; the ledger's uniqueness key.")
    direction: MigrationDirection
    applied_at_iso: str = Field(description="ISO-8601 timestamp, passed in so this stays testable.")
    reversible: Reversibility
    notes: str = ""
