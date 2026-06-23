"""
Module: test_boot_smoke
Layer: test
Purpose: Boot smoke — verifies create_app() builds without import errors and
         that /health is registered and returns 200 without any DB/LLM calls.
Dependencies: unittest.mock, fastapi.testclient, npc_engine.main, npc_engine.config
Used by: pytest (unit suite); make smoke
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SETTINGS = Settings(
    NEO4J_URI="bolt://localhost:7687",
    API_KEY_SECRET="test-smoke-key-000",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_app_returns_fastapi_instance() -> None:
    """create_app() must return a FastAPI instance without raising."""
    with patch("npc_engine.main.get_settings", return_value=_MINIMAL_SETTINGS):
        from npc_engine.main import create_app

        app = create_app()

    assert isinstance(app, FastAPI)


def test_health_route_registered_and_returns_200() -> None:
    """/health must be registered and respond 200 with no DB or LLM calls."""
    with patch("npc_engine.main.get_settings", return_value=_MINIMAL_SETTINGS):
        from npc_engine.main import create_app

        app = create_app()

    route_paths = [getattr(r, "path", None) for r in app.routes]
    assert "/health" in route_paths, f"expected /health in routes, got {route_paths}"

    with patch("npc_engine.api.routes.admin.system.get_settings", return_value=_MINIMAL_SETTINGS):
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")

    assert response.status_code == 200
