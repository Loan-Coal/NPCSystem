"""
route_helpers.py - Shared API response and exception mapping helpers.
Layer: api
Purpose: (auto-detected — review)

Does NOT: perform business logic or data access.

Dependencies injected: None.
"""

from typing import Any, TypeVar

from fastapi import HTTPException

from npc_engine.utils.errors import (
    FactionMembershipError,
    FactionNotFoundError,
    ImmutableFieldError,
    NodeNotFoundError,
    RegistryPayloadValidationError,
    ReputationNotFoundError,
    SchemaValidationError,
)


T = TypeVar("T")


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


def graph_error_to_http(error: Exception) -> HTTPException:
    """Map graph route domain errors to stable HTTP status codes.

    Args:
        error: Domain exception raised by a graph service method.

    Returns:
        HTTPException with an appropriate status code and detail message.
    """
    if isinstance(error, NodeNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, FactionNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, FactionMembershipError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ReputationNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ImmutableFieldError, SchemaValidationError, RegistryPayloadValidationError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Internal server error")
