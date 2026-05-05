"""
test_auth_observability_middleware_v14.py - Tests middleware request correlation and observability metrics.

Does NOT: exercise graph/database dependencies.

Dependencies injected: Settings via middleware constructor.
"""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.config import Settings
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


AUTH_SECRET = "local_dev_secret_change_this_2026"
AUTH_HEADER = {"Authorization": f"Bearer {AUTH_SECRET}"}


def _build_app() -> FastAPI:
    app = FastAPI()
    settings = Settings(
        API_KEY_SECRET=AUTH_SECRET,
        IDEMPOTENCY_ENFORCE_HEADER=True,
        IDEMPOTENCY_HEADER_NAME="X-Idempotency-Key",
    )
    app.add_middleware(ApiKeyMiddleware, settings=settings, idempotency_service=None)

    @app.post("/v1/echo-request-id")
    async def echo_request_id(request: Request) -> dict[str, str]:
        return {"request_id": getattr(request.state, "request_id", "")}

    @app.post("/v1/dialogue")
    async def dialogue() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/v1/raise")
    async def raise_error() -> dict[str, bool]:
        raise RuntimeError("boom")

    return app


def setup_function() -> None:
    reset_metrics_registry()


def test_middleware_sets_request_id_when_header_is_missing() -> None:
    """Middleware should provide request correlation id for downstream handlers."""

    client = TestClient(_build_app())

    response = client.post(
        "/v1/echo-request-id",
        headers={**AUTH_HEADER, "X-Idempotency-Key": "d2719e2d-55ec-4c95-9bdb-22380d73155d"},
    )

    assert response.status_code == 200
    assert response.json()["request_id"].startswith("req:")


def test_missing_idempotency_key_increments_validation_failure_metric() -> None:
    """Required idempotency header failures should increment validation metric."""

    client = TestClient(_build_app())

    response = client.post("/v1/dialogue", headers=AUTH_HEADER)

    metric_value = get_counter_value(
        "validation_failures_total",
        labels={"route": "dialogue", "reason": "idempotency_key_required", "status": "400"},
    )

    assert response.status_code == 400
    assert metric_value == 1.0


def test_unhandled_route_exception_records_server_error_request_metric() -> None:
    """Unhandled downstream errors should still emit request observability metrics."""

    client = TestClient(_build_app(), raise_server_exceptions=False)

    response = client.post(
        "/v1/raise",
        headers={**AUTH_HEADER, "X-Idempotency-Key": "d2719e2d-55ec-4c95-9bdb-22380d73155d"},
    )

    requests_metric = get_counter_value(
        "http_requests_total",
        labels={"route": "raise", "method": "post", "result": "server_error"},
    )

    assert response.status_code == 500
    assert requests_metric == 1.0
