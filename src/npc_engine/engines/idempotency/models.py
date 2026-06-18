"""
Module: idempotency.models
Layer: engines
Purpose: Engine-layer data models for idempotency preflight decisions.
         IdempotencyRecord lives in graph.idempotency_models (graph layer).
Does NOT: perform database I/O or define persistence models.
Dependencies injected: None.
Used by: engines.idempotency.service, engines.idempotency.service_helpers
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


IdempotencyStatus = Literal["pending", "completed", "failed_terminal"]
PreflightDecision = Literal["proceed", "replay", "conflict", "in_flight"]


class IdempotencyPreflightResult(BaseModel):
    """Decision payload returned by idempotency preflight evaluation."""

    decision: PreflightDecision
    request_hash: str
    response_status_code: int | None = None
    response_body: str | None = None
    pending_timeout_seconds: int | None = None

    model_config = ConfigDict(frozen=True, extra="forbid")
