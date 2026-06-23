"""
Package: errors
Layer: api
Purpose: Unified error envelope models and exception handler registration for the API layer.
Public surface: ErrorBody, ErrorDetail, ErrorEnvelope, register_exception_handlers.
Does NOT: define routes, middleware, or business logic.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .error_envelope import ErrorBody, ErrorDetail, ErrorEnvelope
from .exception_handlers import register_exception_handlers

__all__ = [
    "ErrorBody",
    "ErrorDetail",
    "ErrorEnvelope",
    "register_exception_handlers",
]
