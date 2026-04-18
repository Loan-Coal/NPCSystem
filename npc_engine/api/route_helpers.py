"""
route_helpers.py - Shared API response and exception mapping helpers.

Does NOT: perform business logic or data access.

Dependencies injected: None.
"""

from typing import Any

from fastapi import HTTPException

from utils.errors import ImmutableFieldError, NodeNotFoundError, SchemaValidationError


def ok_response(data: Any, meta: Any | None = None) -> dict[str, Any]:
    """Build the canonical success response envelope."""

    return {"success": True, "data": data, "meta": meta}


def graph_error_to_http(error: Exception) -> HTTPException:
    """Map graph route domain errors to stable HTTP status codes."""

    if isinstance(error, NodeNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ImmutableFieldError, SchemaValidationError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Internal server error")
