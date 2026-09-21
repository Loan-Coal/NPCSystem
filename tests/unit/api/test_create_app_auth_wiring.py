"""
Module: tests.unit.api.test_create_app_auth_wiring
Layer: tests
Purpose: Verifies that create_app() assembles the ApiKeyMiddleware correctly so that
         a future change reordering or removing the middleware causes this suite to go red.
         Routes are driven mechanically from the app's router table rather than
         hardcoded so adding a router group does not silently escape the gate.
Does NOT: start Neo4j, Redis, Ollama, or any lifespan dependency.
Dependencies: fastapi.testclient, npc_engine.main.create_app, unittest.mock
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from npc_engine.auth.middleware_helpers import is_public_path
from npc_engine.config import Settings

_TEST_KEY = "local_dev_secret_change_this_2026"
_AUTH_HEADER = {"Authorization": f"Bearer {_TEST_KEY}"}

# The dev-env public HTTP surface, pinned so that widening is_public_path cannot silently
# drop a route out of the 401 test below. /setup/* is public in dev only (ISSUE-227).
_EXPECTED_PUBLIC = frozenset({"/health", "/readiness", "/setup/config", "/setup/validate"})


@contextmanager
def _stubbed_create_app() -> Iterator[object]:
    """Yield a create_app() app with external singletons mocked to avoid I/O."""
    settings = Settings(API_KEY_SECRET=_TEST_KEY)
    with (
        patch("npc_engine.main.get_settings", return_value=settings),
        patch("npc_engine.main.get_idempotency_service", return_value=None),
    ):
        from npc_engine.main import create_app
        yield create_app()


def _non_public_http_routes(app: object) -> list[tuple[str, str]]:
    """Return (path, method) pairs for non-public HTTP routes in the router table.

    Selects one representative route per second-segment prefix group so new router
    groups are automatically included without any manual update to this module.
    Routes with path parameters are skipped to keep requests parameter-free.
    """
    seen_prefixes: set[str] = set()
    sampled: list[tuple[str, str]] = []
    for route in app.routes:  # type: ignore[attr-defined]
        if not isinstance(route, APIRoute) or not route.methods:
            continue
        if is_public_path(route.path, env="dev"):
            continue
        if "{" in route.path:
            continue
        parts = route.path.strip("/").split("/")
        prefix = parts[1] if len(parts) > 1 else parts[0]
        if prefix in seen_prefixes:
            continue
        method = "GET" if "GET" in route.methods else next(iter(route.methods))
        seen_prefixes.add(prefix)
        sampled.append((route.path, method))
    return sampled


def _all_protected_http_routes(app: object) -> list[tuple[str, str]]:
    """Return (path, method) for EVERY non-public HTTP route, path params filled with 'x'.

    The middleware rejects before routing resolves parameters, so a filled path is a
    faithful probe of the auth gate for parameterised routes too.
    """
    return [
        (re.sub(r"\{[^}]+\}", "x", route.path), sorted(route.methods)[0])
        for route in app.routes  # type: ignore[attr-defined]
        if isinstance(route, APIRoute)
        and route.methods
        and not is_public_path(route.path, env="dev")
    ]


@pytest.fixture(scope="module")
def _app() -> object:
    with _stubbed_create_app() as app:
        return app


@pytest.fixture(scope="module")
def _protected_routes(_app: object) -> list[tuple[str, str]]:
    routes = _non_public_http_routes(_app)
    assert routes, "router table returned no non-public routes — check create_app() setup"
    return routes


# ---------------------------------------------------------------------------
# Public surface — /health must be reachable without credentials
# ---------------------------------------------------------------------------


def test_health_accessible_without_credentials(_app: object) -> None:
    """GET /health succeeds with no Authorization header."""
    client = TestClient(_app, raise_server_exceptions=False)
    response = client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Protected surface — all sampled route groups require credentials
# ---------------------------------------------------------------------------


def test_public_route_set_is_pinned(_app: object) -> None:
    """Exactly the pinned paths are exempt — a new exemption must be a deliberate edit here."""
    public = {
        route.path
        for route in _app.routes  # type: ignore[attr-defined]
        if isinstance(route, APIRoute) and is_public_path(route.path, env="dev")
    }
    assert public == _EXPECTED_PUBLIC


def test_protected_routes_return_401_without_credentials(_app: object) -> None:
    """Every non-public HTTP route, parameterised ones included, rejects a missing API key."""
    client = TestClient(_app, raise_server_exceptions=False)
    failures: list[str] = []
    for path, method in _all_protected_http_routes(_app):
        response = client.request(method, path)
        if response.status_code != 401:
            failures.append(f"{method} {path} → {response.status_code} (expected 401)")
    assert not failures, "Routes missing auth gate:\n" + "\n".join(failures)


def test_valid_key_bypasses_auth_on_protected_routes(
    _app: object, _protected_routes: list[tuple[str, str]]
) -> None:
    """A valid API key does not yield 401 or 403 on any sampled route."""
    client = TestClient(_app, raise_server_exceptions=False)
    failures: list[str] = []
    for path, method in _protected_routes:
        response = client.request(method, path, headers=_AUTH_HEADER)
        if response.status_code in (401, 403):
            failures.append(f"{method} {path} → {response.status_code}")
    assert not failures, "Valid key still rejected:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# Error envelope format — 401 carries only error metadata, no data payload
# ---------------------------------------------------------------------------


def test_401_carries_error_envelope_not_data_payload(
    _app: object, _protected_routes: list[tuple[str, str]]
) -> None:
    """Unauthorized responses expose error metadata only — no resource data leaks."""
    client = TestClient(_app, raise_server_exceptions=False)
    path, method = _protected_routes[0]
    response = client.request(method, path)
    assert response.status_code == 401
    body = response.json()
    assert "error" in body, f"401 body missing 'error' key: {body}"
    assert body.get("data") is None, f"401 body must not carry 'data': {body}"
