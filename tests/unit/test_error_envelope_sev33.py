"""
Tests for SEV-33 unified ErrorEnvelope across all API error responses.

Verifies that:
- RequestValidationError → 422 with code="validation_error"
- HTTPException (401) → 422 with code="http_401"
- Unhandled Exception → 500 with code="internal_error", no stack trace in body
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from npc_engine.api.error_envelope import ErrorBody, ErrorDetail, ErrorEnvelope
from npc_engine.main import (
    _http_error_handler,
    _internal_error_handler,
    _validation_error_handler,
)


# ---------------------------------------------------------------------------
# Helpers — minimal test app with handlers registered
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the three SEV-33 exception handlers."""
    app = FastAPI()
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)
    return app


# ---------------------------------------------------------------------------
# Unit tests — ErrorEnvelope / ErrorBody / ErrorDetail schema
# ---------------------------------------------------------------------------


class TestErrorEnvelopeSchema:
    """ErrorEnvelope serialises to the expected dict shape."""

    def test_minimal_envelope(self) -> None:
        env = ErrorEnvelope(error=ErrorBody(code="some_error", message="something went wrong"))
        data = env.model_dump()
        assert data == {"error": {"code": "some_error", "message": "something went wrong", "details": []}}

    def test_envelope_with_details(self) -> None:
        detail = ErrorDetail(field="player_id", reason="field required")
        env = ErrorEnvelope(error=ErrorBody(code="validation_error", message="bad input", details=[detail]))
        data = env.model_dump()
        assert data["error"]["details"] == [{"field": "player_id", "reason": "field required"}]

    def test_detail_field_is_optional(self) -> None:
        detail = ErrorDetail(reason="body required")
        assert detail.field is None
        assert detail.reason == "body required"


# ---------------------------------------------------------------------------
# Integration tests — exception handlers via TestClient
# ---------------------------------------------------------------------------


class TestValidationErrorHandler:
    """422 validation errors are wrapped in ErrorEnvelope."""

    def test_missing_required_field_returns_422_envelope(self) -> None:
        app = _make_test_app()

        from pydantic import BaseModel

        class Body(BaseModel):
            name: str

        @app.post("/test-validate")
        async def _route(body: Body) -> dict:
            return {"name": body.name}

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/test-validate", json={})
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "validation_error"
        assert data["error"]["message"] == "request validation failed"
        assert isinstance(data["error"]["details"], list)
        assert len(data["error"]["details"]) >= 1
        # No raw FastAPI detail list at top level
        assert "detail" not in data

    def test_validation_error_detail_contains_field_and_reason(self) -> None:
        app = _make_test_app()

        from pydantic import BaseModel
        from typing import Literal

        class Body(BaseModel):
            status: Literal["active", "inactive"]

        @app.post("/test-validate2")
        async def _route2(body: Body) -> dict:
            return {"status": body.status}

        client = TestClient(app, raise_server_exceptions=False)
        # Send a value that is not one of the allowed Literals — Pydantic v2 always rejects this
        resp = client.post("/test-validate2", json={"status": "invalid_literal_value"})
        assert resp.status_code == 422
        details = resp.json()["error"]["details"]
        assert len(details) >= 1
        assert all("field" in d and "reason" in d for d in details)


class TestHttpErrorHandler:
    """HTTP exceptions are wrapped in ErrorEnvelope with code http_<status>."""

    def test_401_raises_http_error(self) -> None:
        app = _make_test_app()

        @app.get("/test-401")
        async def _route() -> dict:
            raise HTTPException(status_code=401, detail="Unauthorized")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-401")
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "http_401"
        assert "detail" not in data

    def test_403_raises_http_error(self) -> None:
        app = _make_test_app()

        @app.get("/test-403")
        async def _route() -> dict:
            raise HTTPException(status_code=403, detail="Forbidden")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-403")
        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["code"] == "http_403"

    def test_404_raises_http_error(self) -> None:
        app = _make_test_app()

        @app.get("/test-404")
        async def _route() -> dict:
            raise HTTPException(status_code=404, detail="npc not found")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-404")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "http_404"
        assert data["error"]["message"] == "npc not found"


class TestInternalErrorHandler:
    """Unhandled exceptions return 500 without leaking stack traces."""

    def test_unhandled_exception_returns_500(self) -> None:
        app = _make_test_app()

        @app.get("/test-500")
        async def _route() -> dict:
            raise RuntimeError("something exploded internally")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-500")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"]["code"] == "internal_error"
        assert data["error"]["message"] == "internal error"

    def test_unhandled_exception_does_not_leak_stack_trace(self) -> None:
        app = _make_test_app()

        @app.get("/test-500-safe")
        async def _route() -> dict:
            raise ValueError("secret_internal_detail_must_not_leak")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test-500-safe")
        body_text = resp.text
        assert "secret_internal_detail_must_not_leak" not in body_text
        assert "Traceback" not in body_text
