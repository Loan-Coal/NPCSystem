"""
Module: api.error_envelope
Layer: api
Purpose: Canonical error response envelope for all API error responses.
         Ensures integrators see a single consistent error shape regardless of
         whether the error originates from validation, auth, or application logic.
Does NOT: contain business logic, call LLMs, or access the graph.
Dependencies injected: None.
Used by: npc_engine.main (exception handlers), npc_engine.auth.middleware,
         npc_engine.auth.middleware_helpers
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """One field-level validation detail within an error response.

    Attributes:
        field: Dot-path of the offending field, or None for non-field errors.
        reason: Human-readable description of why the field was rejected.
    """

    field: str | None = None
    reason: str


class ErrorBody(BaseModel):
    """Error payload carried inside the top-level ErrorEnvelope.

    Attributes:
        code: Machine-readable error code (e.g. "validation_error", "http_401").
        message: Human-readable summary of the error.
        details: Optional list of field-level validation details.
    """

    code: str
    message: str
    details: list[ErrorDetail] = []


class ErrorEnvelope(BaseModel):
    """Top-level error response envelope sent on all 4xx/5xx responses.

    Integrators should check ``response["error"]["code"]`` to identify errors.

    Attributes:
        error: Structured error body.
    """

    error: ErrorBody
