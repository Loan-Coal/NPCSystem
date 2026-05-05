"""
models.py - Typed data models for idempotency records and preflight decisions.

Does NOT: perform database I/O.

Dependencies injected: None.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


IdempotencyStatus = Literal["pending", "completed", "failed_terminal"]
PreflightDecision = Literal["proceed", "replay", "conflict", "in_flight"]


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


class IdempotencyPreflightResult(BaseModel):
    """Decision payload returned by idempotency preflight evaluation."""

    decision: PreflightDecision
    request_hash: str
    response_status_code: int | None = None
    response_body: str | None = None
    pending_timeout_seconds: int | None = None

    model_config = ConfigDict(frozen=True, extra="forbid")
