"""
test_auth_idempotency_middleware_v14.py - Unit tests for v1.4 idempotency header preflight.

Does NOT: exercise graph/database dependencies.

Dependencies injected: Settings via middleware constructor.
"""

from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.testclient import TestClient

from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.config import Settings
from npc_engine.engines.idempotency.models import IdempotencyPreflightResult


AUTH_SECRET = "local_dev_secret_change_this_2026"
AUTH_HEADER = {"Authorization": f"Bearer {AUTH_SECRET}"}


class _IdempotencyServiceStub:
    def __init__(self, preflight_result: IdempotencyPreflightResult):
        self.preflight_result = preflight_result
        self.finalize_calls = 0
        self.preflight_payloads: list[dict] = []
        self.finalize_payloads: list[dict] = []

    async def preflight(self, **kwargs) -> IdempotencyPreflightResult:
        self.preflight_payloads.append(kwargs)
        return self.preflight_result

    async def finalize(self, **kwargs) -> None:
        self.finalize_calls += 1
        self.finalize_payloads.append(kwargs)


def _build_app(
    enforce_idempotency: bool,
    header_name: str = "X-Idempotency-Key",
    idempotency_service=None,
) -> FastAPI:
    app = FastAPI()
    settings = Settings(
        API_KEY_SECRET=AUTH_SECRET,
        IDEMPOTENCY_ENFORCE_HEADER=enforce_idempotency,
        IDEMPOTENCY_HEADER_NAME=header_name,
    )
    app.add_middleware(
        ApiKeyMiddleware,
        settings=settings,
        idempotency_service=idempotency_service,
    )

    @app.post("/v1/dialogue")
    async def dialogue() -> dict:
        return {"ok": True}

    @app.post("/v1/idempotency-state")
    async def idempotency_state(request: Request) -> dict:
        return {
            "ok": True,
            "idempotency_key": getattr(request.state, "idempotency_key", ""),
            "idempotency_request_hash": getattr(request.state, "idempotency_request_hash", ""),
        }

    @app.get("/v1/schema")
    async def schema() -> dict:
        return {"ok": True}

    @app.options("/v1/dialogue")
    async def dialogue_options() -> dict:
        return {"ok": True}

    @app.post("/v10/dialogue")
    async def dialogue_v10() -> dict:
        return {"ok": True}

    return app


def test_mutating_request_without_x_idempotency_key_returns_400_idempotency_key_required() -> None:
    """POST requests should fail fast when idempotency header is missing."""

    client = TestClient(_build_app(enforce_idempotency=True))

    response = client.post("/v1/dialogue", headers=AUTH_HEADER)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_mutating_request_with_invalid_idempotency_key_returns_422() -> None:
    """POST requests should reject non-UUIDv4 idempotency keys."""

    client = TestClient(_build_app(enforce_idempotency=True))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": "not-a-uuid"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_mutating_request_with_valid_uuid_v4_key_passes() -> None:
    """POST requests should pass preflight when a UUIDv4 idempotency key is supplied."""

    client = TestClient(_build_app(enforce_idempotency=True))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_options_preflight_bypasses_idempotency_header_check_for_v1_mutating_paths() -> None:
    """OPTIONS preflight should bypass idempotency checks."""

    client = TestClient(_build_app(enforce_idempotency=True))

    response = client.options("/v1/dialogue", headers=AUTH_HEADER)

    assert response.status_code == 200


def test_idempotency_check_can_be_disabled_for_safe_rollout() -> None:
    """When enforcement is disabled, mutating routes should preserve v1.3 behavior."""

    client = TestClient(_build_app(enforce_idempotency=False))

    response = client.post("/v1/dialogue", headers=AUTH_HEADER)

    assert response.status_code == 200


def test_idempotency_enforcement_does_not_apply_to_v10_routes() -> None:
    """Only /v1/* mutating routes should be included in v1.4 preflight checks."""

    client = TestClient(_build_app(enforce_idempotency=True))

    response = client.post("/v10/dialogue", headers=AUTH_HEADER)

    assert response.status_code == 200


def test_idempotency_error_message_uses_configured_header_name() -> None:
    """Error payload should reference configured header names for clarity."""

    custom_header_name = "X-Custom-Idempotency"
    client = TestClient(_build_app(enforce_idempotency=True, header_name=custom_header_name))

    response = client.post("/v1/dialogue", headers=AUTH_HEADER)

    assert response.status_code == 400
    assert response.json()["error"]["message"] == f"{custom_header_name} header is required."


def test_preflight_replay_returns_cached_response_without_calling_route() -> None:
    """Replay decision should return cached payload and skip route logic execution."""

    service = _IdempotencyServiceStub(
        preflight_result=IdempotencyPreflightResult(
            decision="replay",
            request_hash="hash-1",
            response_status_code=201,
            response_body='{"cached": true}',
        )
    )
    client = TestClient(_build_app(enforce_idempotency=True, idempotency_service=service))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == 201
    assert response.json() == {"cached": True}
    assert service.finalize_calls == 0


def test_preflight_conflict_returns_409_contract_error() -> None:
    """Conflict decision should return stable 409 contract response."""

    service = _IdempotencyServiceStub(
        preflight_result=IdempotencyPreflightResult(
            decision="conflict",
            request_hash="hash-1",
        )
    )
    client = TestClient(_build_app(enforce_idempotency=True, idempotency_service=service))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_preflight_in_flight_returns_409_contract_error() -> None:
    """In-flight decision should return stable 409 contract response."""

    service = _IdempotencyServiceStub(
        preflight_result=IdempotencyPreflightResult(
            decision="in_flight",
            request_hash="hash-1",
            pending_timeout_seconds=30,
        )
    )
    client = TestClient(_build_app(enforce_idempotency=True, idempotency_service=service))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_FLIGHT"


def test_preflight_proceed_triggers_finalize_after_route_execution() -> None:
    """Proceed decision should execute route and then finalize persistent record."""

    service = _IdempotencyServiceStub(
        preflight_result=IdempotencyPreflightResult(
            decision="proceed",
            request_hash="hash-1",
        )
    )
    client = TestClient(_build_app(enforce_idempotency=True, idempotency_service=service))

    response = client.post(
        "/v1/dialogue",
        headers={**AUTH_HEADER, "X-Idempotency-Key": str(uuid4())},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert service.finalize_calls == 1
    assert service.preflight_payloads[0]["method"] == "POST"
    assert service.preflight_payloads[0]["path"] == "/v1/dialogue"
    assert service.finalize_payloads[0]["status_code"] == 200
    assert service.finalize_payloads[0]["request_hash"] == "hash-1"


def test_valid_idempotency_key_is_exposed_on_request_state_for_downstream_paths() -> None:
    service = _IdempotencyServiceStub(
        preflight_result=IdempotencyPreflightResult(
            decision="proceed",
            request_hash="hash-123",
        )
    )
    key = str(uuid4())
    client = TestClient(_build_app(enforce_idempotency=True, idempotency_service=service))

    response = client.post(
        "/v1/idempotency-state",
        headers={**AUTH_HEADER, "X-Idempotency-Key": key},
    )

    assert response.status_code == 200
    assert response.json()["idempotency_key"] == key
    assert response.json()["idempotency_request_hash"] == "hash-123"
