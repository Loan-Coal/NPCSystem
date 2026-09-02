"""
test_graph_outage_503.py - Tests the Neo4j outage -> HTTP 503 contract (R3.2).

Does NOT: touch a real Neo4j server; the driver-boundary translation is covered
by tests/integration/test_graph_outage.py.

Dependencies injected: a minimal FastAPI app wired by register_exception_handlers.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.errors.exception_handlers import register_exception_handlers
from npc_engine.utils.errors import GraphUnavailableError


_BOLT_URI = "bolt://internal-neo4j:7687"
_EXPECTED_BODY = {
    "error": {
        "code": "graph_unavailable",
        "message": "graph database unavailable",
        "details": [],
    }
}


def _app_that_hits_an_outage() -> FastAPI:
    """Build an app whose one route fails the way a graph outage fails."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise GraphUnavailableError(uri=_BOLT_URI, cause="connection refused")

    return app


@pytest.fixture()
def client() -> TestClient:
    """Return a client that lets registered handlers answer instead of re-raising."""
    return TestClient(_app_that_hits_an_outage(), raise_server_exceptions=False)


def test_graph_outage_returns_503(client: TestClient) -> None:
    """A graph outage is retryable, so it must not share 500 with a broken request.

    Before R3.2 no handler was registered for GraphUnavailableError, so the
    Exception catch-all answered 500 and the Unreal client could not tell "retry
    in a moment" from "your request is malformed".
    """
    response = client.get("/boom")

    assert response.status_code == 503


def test_graph_outage_body_is_the_canonical_error_envelope(client: TestClient) -> None:
    """The body must be an ErrorEnvelope, never a canned dialogue reply.

    This is the half that guards against regressing to R3.1's failure, where the
    degradation ladder swallowed the outage and served a successful HTTP 200.
    """
    response = client.get("/boom")

    assert response.json() == _EXPECTED_BODY


def test_graph_outage_does_not_leak_the_bolt_uri(client: TestClient) -> None:
    """Never echo a domain error's __str__ to the client (L1-02 / SEV-16).

    GraphUnavailableError renders its uri and cause, which would hand a caller the
    internal bolt endpoint.
    """
    response = client.get("/boom")

    assert _BOLT_URI not in response.text
    assert "connection refused" not in response.text
