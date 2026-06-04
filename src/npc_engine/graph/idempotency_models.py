"""
Module: idempotency_models
Layer: graph
Purpose: Typed data models for idempotency records stored in Neo4j.
Does NOT: perform database I/O.
Dependencies injected: None.
Used by: graph.idempotency_writer, graph.idempotency_queries,
         engines.idempotency.store_protocol, engines.idempotency.service_helpers
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


IdempotencyStatus = Literal["pending", "completed", "failed_terminal"]


class IdempotencyRecord(BaseModel):
    """Persistent idempotency record stored in Neo4j."""

    idempotency_key: str
    resource_scope: str
    request_hash: str
    status: IdempotencyStatus
    response_status_code: int | None = None
    response_body: str | None = None
    response_hash: str | None = None
    created_at: str
    expires_at: str
    pending_timeout_seconds: int
    updated_at: str | None = None

    model_config = ConfigDict(frozen=True, extra="forbid")
