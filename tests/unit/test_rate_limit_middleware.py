"""
test_rate_limit_middleware.py - Unit tests for token-bucket rate-limit middleware.

Does NOT: exercise graph or auth dependencies.

Dependencies injected: Settings via middleware constructor.
"""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.rate_limit import RateLimitMiddleware, _TokenBucket
from npc_engine.config import Settings

AUTH_SECRET = "local_dev_secret_change_this_2026"
AUTH_HEADER = {"Authorization": f"Bearer {AUTH_SECRET}"}


# ---------------------------------------------------------------------------
# _TokenBucket unit tests
# ---------------------------------------------------------------------------


def test_bucket_allows_requests_within_capacity() -> None:
    """A full bucket should allow up to capacity consecutive requests."""

    bucket = _TokenBucket(rate=10.0, capacity=3.0)

    assert bucket.consume() is True
    assert bucket.consume() is True
    assert bucket.consume() is True


def test_bucket_rejects_request_when_empty() -> None:
    """An exhausted bucket should reject further requests."""

    bucket = _TokenBucket(rate=0.01, capacity=2.0)
    bucket.consume()
    bucket.consume()

    assert bucket.consume() is False


def test_bucket_recovers_after_wait() -> None:
    """Bucket should refill proportionally to elapsed time."""

    bucket = _TokenBucket(rate=100.0, capacity=1.0)
    bucket.consume()  # exhaust

    # Travel forward in time by patching _last_refill
    bucket._last_refill -= 0.02  # 20 ms → at 100 req/s adds 2 tokens

    assert bucket.consume() is True


def test_bucket_never_exceeds_capacity() -> None:
    """Token count should be capped at capacity even after long idle."""

    bucket = _TokenBucket(rate=100.0, capacity=5.0)
    bucket._last_refill -= 1_000_000  # very long idle
    bucket._tokens = 0.0  # start empty to force refill path

    bucket.consume()  # triggers refill → clamped to 5, then -1 = 4
    assert bucket._tokens <= 5.0


# ---------------------------------------------------------------------------
# Middleware integration tests
# ---------------------------------------------------------------------------


def _build_app(
    rate: float = 100.0,
    burst: int = 5,
    enabled: bool = True,
) -> FastAPI:
    app = FastAPI()
    settings = Settings(
        API_KEY_SECRET=AUTH_SECRET,
        RATE_LIMIT_ENABLED=enabled,
        RATE_LIMIT_REQUESTS_PER_SECOND=rate,
        RATE_LIMIT_BURST_SIZE=burst,
    )
    app.add_middleware(RateLimitMiddleware, settings=settings)

    @app.get("/v1/ping")
    async def ping() -> dict:
        return {"ok": True}

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True}

    return app


def test_requests_within_burst_are_allowed() -> None:
    """Requests within burst capacity should all return 200."""

    client = TestClient(_build_app(rate=100.0, burst=3))

    for _ in range(3):
        response = client.get("/v1/ping", headers=AUTH_HEADER)
        assert response.status_code == 200


def test_requests_over_limit_return_429() -> None:
    """Requests beyond burst capacity should be rejected with 429."""

    client = TestClient(_build_app(rate=0.001, burst=2))

    client.get("/v1/ping", headers=AUTH_HEADER)
    client.get("/v1/ping", headers=AUTH_HEADER)
    response = client.get("/v1/ping", headers=AUTH_HEADER)

    assert response.status_code == 429
    assert response.json()["error"] == "RATE_LIMIT_EXCEEDED"


def test_health_endpoint_is_exempt_from_rate_limiting() -> None:
    """The /health path should never be blocked even when bucket is empty."""

    client = TestClient(_build_app(rate=0.001, burst=1))

    client.get("/v1/ping", headers=AUTH_HEADER)  # exhaust bucket

    response = client.get("/health")

    assert response.status_code == 200


def test_rate_limit_disabled_allows_unlimited_requests() -> None:
    """When RATE_LIMIT_ENABLED=false no requests should be throttled."""

    client = TestClient(_build_app(rate=0.001, burst=1, enabled=False))

    for _ in range(20):
        response = client.get("/v1/ping", headers=AUTH_HEADER)
        assert response.status_code == 200


def test_different_api_keys_have_independent_buckets() -> None:
    """Two distinct API keys should not share rate-limit state."""

    app = FastAPI()
    settings = Settings(
        API_KEY_SECRET=AUTH_SECRET,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_REQUESTS_PER_SECOND=0.001,
        RATE_LIMIT_BURST_SIZE=1,
    )
    app.add_middleware(RateLimitMiddleware, settings=settings)

    @app.get("/v1/ping")
    async def ping() -> dict:
        return {"ok": True}

    client = TestClient(app)

    # Exhaust key A's bucket
    client.get("/v1/ping", headers={"Authorization": "Bearer key-A"})

    # Key B should still have a full bucket
    response = client.get("/v1/ping", headers={"Authorization": "Bearer key-B"})
    assert response.status_code == 200
