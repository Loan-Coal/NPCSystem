"""
route_helpers.py - Shared API response and exception mapping helpers.
Layer: api
Purpose: Build canonical success/error envelopes and map graph domain errors to
         redacted HTTP responses.
Does NOT: perform business logic or data access.
Dependencies injected: None.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel

from npc_engine.utils.errors import (
    FactionMembershipError,
    FactionNotFoundError,
    ImmutableFieldError,
    NodeNotFoundError,
    RegistryPayloadValidationError,
    ReputationNotFoundError,
    SchemaValidationError,
)
from npc_engine.utils.logging import get_logger


T = TypeVar("T")
DataT = TypeVar("DataT")

logger = get_logger(__name__)


class OkEnvelope(BaseModel, Generic[DataT]):
    """Canonical success envelope for typed OpenAPI route bodies.

    Used purely as a route `response_model` so generated clients receive a real
    schema. The runtime path stays `ok_response()` (a plain dict) — FastAPI
    validates the dict against this model on the way out. No runtime behaviour
    change.
    """

    success: bool = True
    data: DataT
    meta: dict[str, Any] | None = None


class ErrEnvelope(BaseModel):
    """Canonical error envelope for documented (non-2xx) route responses."""

    success: bool = False
    error: str
    message: str
    detail: Any | None = None

# Redacted, stable client-facing details (L1-02 / SEV-16): never echo a domain
# error's __str__, which carries internal node ids, type labels, and schema paths.
_NOT_FOUND_DETAIL = "Resource not found"
_IMMUTABLE_FIELD_DETAIL = "Field cannot be modified"
_INTERNAL_DETAIL = "Internal server error"

# 404 family: fully opaque so a caller cannot enumerate graph topology by probing.
_NOT_FOUND_ERRORS = (
    NodeNotFoundError,
    FactionNotFoundError,
    FactionMembershipError,
    ReputationNotFoundError,
)


def ok_response(data: Any, meta: Any | None = None) -> dict[str, Any]:
    """Build the canonical success response envelope.

    Args:
        data: Response payload.
        meta: Optional metadata dict (pagination, warnings, etc.).

    Returns:
        Dict with success=True, data, and meta fields.
    """
    return {"success": True, "data": data, "meta": meta}


def error_response(*, error_code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    """Build the canonical error response envelope.

    Args:
        error_code: Machine-readable error code string.
        message: Human-readable error description.
        detail: Optional structured detail payload.

    Returns:
        Dict with success=False, error, message, and optional detail fields.
    """
    payload: dict[str, Any] = {
        "success": False,
        "error": error_code,
        "message": message,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def require_node(node: T | None, *, node_type: str) -> T:
    """Raise 404 when node is missing, otherwise return the node payload.

    Args:
        node: Node payload or None.
        node_type: Human-readable node type label for the 404 message.

    Returns:
        The node payload when present.

    Raises:
        HTTPException: 404 when node is None.
    """
    if node is None:
        raise HTTPException(status_code=404, detail=f"{node_type} not found")
    return node


def _safe_validation_detail(error: Exception) -> str:
    """Return caller-relevant validation feedback with no internal paths/labels.

    422s legitimately tell an integrator what was wrong with their payload, but we
    expose only caller-supplied context (codes, field-level messages) — never the
    error class repr, a node id, or a filesystem schema path.
    """
    if isinstance(error, RegistryPayloadValidationError):
        return f"{error.code}: {error.detail}"
    if isinstance(error, SchemaValidationError):
        return error.detail
    return _IMMUTABLE_FIELD_DETAIL


def graph_error_to_http(error: Exception) -> HTTPException:
    """Map graph route domain errors to redacted HTTP responses.

    The full structured error is logged server-side; the client receives a
    redacted detail so internal node ids/type labels/schema paths never leak
    (L1-02 / SEV-16). 404s are fully opaque to block topology enumeration; 422s
    expose only caller-relevant validation feedback.

    Args:
        error: Domain exception raised by a graph service method.
    Returns:
        HTTPException with an appropriate status code and a redacted detail.
    """
    if isinstance(error, _NOT_FOUND_ERRORS):
        logger.info("graph_route_not_found", extra={"error": str(error)})
        return HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    if isinstance(error, (ImmutableFieldError, SchemaValidationError, RegistryPayloadValidationError)):
        logger.info("graph_route_validation_error", extra={"error": str(error)})
        return HTTPException(status_code=422, detail=_safe_validation_detail(error))
    logger.error("graph_route_internal_error", extra={"error": str(error)})
    return HTTPException(status_code=500, detail=_INTERNAL_DETAIL)
