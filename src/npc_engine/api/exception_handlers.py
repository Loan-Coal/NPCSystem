"""
Module: exception_handlers
Layer: api
Purpose: Canonical ErrorEnvelope exception handlers and their registration on the app.
Does NOT: define routes, middleware, or business logic; only maps exceptions to ErrorEnvelope responses.
Dependencies injected: fastapi, starlette, api.error_envelope, utils.errors, utils.logging.
Used by: api.main (create_app calls register_exception_handlers).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from npc_engine.api.error_envelope import ErrorBody, ErrorDetail, ErrorEnvelope
from npc_engine.utils.errors import ContentRatingViolationError
from npc_engine.utils.logging import get_logger

_handler_logger = get_logger(__name__)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI RequestValidationError to a canonical ErrorEnvelope (422).

    Args:
        request: Incoming FastAPI request.
        exc: The validation exception raised by FastAPI.

    Returns:
        JSONResponse with ErrorEnvelope shape and HTTP 422 status.
    """
    details = [
        ErrorDetail(field=".".join(str(s) for s in e["loc"]), reason=e["msg"])
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="validation_error",
                message="request validation failed",
                details=details,
            )
        ).model_dump(),
    )


async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to a canonical ErrorEnvelope.

    Args:
        request: Incoming FastAPI request.
        exc: The HTTP exception raised by route handlers or middleware.

    Returns:
        JSONResponse with ErrorEnvelope shape and the exception's status code.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorEnvelope(
            error=ErrorBody(
                code=f"http_{exc.status_code}",
                message=str(exc.detail) if exc.detail else "error",
            )
        ).model_dump(),
    )


async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert unhandled exceptions to a canonical ErrorEnvelope (500).

    Never leaks stack traces or internal details to the caller.

    Args:
        request: Incoming FastAPI request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with ErrorEnvelope shape and HTTP 500 status.
    """
    _handler_logger.error("unhandled_exception", extra={"exc": str(exc)})
    return JSONResponse(
        status_code=500,
        content=ErrorEnvelope(
            error=ErrorBody(code="internal_error", message="internal error")
        ).model_dump(),
    )


async def _content_rating_violation_handler(request: Request, exc: ContentRatingViolationError) -> JSONResponse:
    """Convert ContentRatingViolationError to a canonical ErrorEnvelope (422).

    Args:
        request: Incoming FastAPI request.
        exc: The content rating violation raised by the dialogue handler.

    Returns:
        JSONResponse with ErrorEnvelope shape and HTTP 422 status.
    """
    return JSONResponse(
        status_code=422,
        content=ErrorEnvelope(
            error=ErrorBody(code="content_rating_violation", message=str(exc))
        ).model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the canonical ErrorEnvelope exception handlers on the app.

    Registered before middleware so they apply to all errors.

    Args:
        app: The FastAPI application to attach handlers to.
    """
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ContentRatingViolationError, _content_rating_violation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _internal_error_handler)
