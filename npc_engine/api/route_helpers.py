"""
route_helpers.py - Shared API response and exception mapping helpers.

Does NOT: perform business logic or data access.

Dependencies injected: None.
"""

from typing import Any, TypeVar

from fastapi import HTTPException

from utils.errors import ImmutableFieldError, NodeNotFoundError, SchemaValidationError


T = TypeVar("T")


def ok_response(data: Any, meta: Any | None = None) -> dict[str, Any]:
    """Build the canonical success response envelope."""

    return {"success": True, "data": data, "meta": meta}


def error_response(*, error_code: str, message: str, detail: Any | None = None) -> dict[str, Any]:
    """Build the canonical error response envelope."""

    payload: dict[str, Any] = {
        "success": False,
        "error": error_code,
        "message": message,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def require_node(node: T | None, *, node_type: str) -> T:
    """Raise 404 when node is missing, otherwise return the node payload."""

    if node is None:
        raise HTTPException(status_code=404, detail=f"{node_type} not found")
    return node


def graph_error_to_http(error: Exception) -> HTTPException:
    """Map graph route domain errors to stable HTTP status codes."""

    if isinstance(error, NodeNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ImmutableFieldError, SchemaValidationError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Internal server error")
