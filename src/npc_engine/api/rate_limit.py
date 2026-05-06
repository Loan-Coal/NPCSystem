"""
Module: rate_limit
Layer: api
Purpose: Token-bucket rate-limiter middleware, in-memory, per API key.
Does NOT: authenticate requests or persist rate-limit state across restarts.
Dependencies injected: config.Settings via constructor argument.
Used by: main.py
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from npc_engine.config import Settings

RATE_LIMIT_EXCEEDED_CODE = "RATE_LIMIT_EXCEEDED"
_HTTP_TOO_MANY = 429
_HEALTH_PATH = "/health"


class _TokenBucket:
    """Single token bucket for one API key."""

    def __init__(self, rate: float, capacity: float) -> None:
        """Initialise a full bucket.

        Args:
            rate: Refill rate in tokens per second.
            capacity: Maximum token capacity (also burst size).
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()

    def consume(self) -> bool:
        """Refill proportional to elapsed time, then consume one token.

        Returns:
            True when the request is within the limit; False when throttled.
        """
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global per-API-key token-bucket rate limiter.

    Buckets are keyed by a SHA-256 prefix of the raw Authorization header so
    the plaintext secret is never held in memory beyond the request lifetime.
    The /health path is always exempt.
    """

    def __init__(self, app, settings: Settings) -> None:
        """Initialise with application settings.

        Args:
            app: ASGI application to wrap.
            settings: Application settings supplying rate-limit parameters.
        """
        super().__init__(app)
        self._settings = settings
        self._buckets: dict[str, _TokenBucket] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Apply token-bucket check before forwarding the request.

        Args:
            request: Incoming FastAPI request.
            call_next: ASGI callable that forwards the request to the next layer.

        Returns:
            Response from the next layer, or 429 when the rate limit is exceeded.
        """
        if not self._settings.RATE_LIMIT_ENABLED or request.url.path == _HEALTH_PATH:
            return await call_next(request)

        key_hash = self._bucket_key(request)
        if key_hash not in self._buckets:
            self._buckets[key_hash] = _TokenBucket(
                rate=self._settings.RATE_LIMIT_REQUESTS_PER_SECOND,
                capacity=float(self._settings.RATE_LIMIT_BURST_SIZE),
            )

        if not self._buckets[key_hash].consume():
            return JSONResponse(
                status_code=_HTTP_TOO_MANY,
                content={
                    "success": False,
                    "error": RATE_LIMIT_EXCEEDED_CODE,
                    "message": "Rate limit exceeded. Retry after the current window expires.",
                },
            )

        return await call_next(request)

    @staticmethod
    def _bucket_key(request: Request) -> str:
        """Derive a stable, non-reversible bucket key from the Authorization header.

        Args:
            request: Incoming FastAPI request.

        Returns:
            First 16 hex chars of the SHA-256 digest of the Authorization value,
            or the literal string 'anonymous' when no header is present.
        """
        raw = request.headers.get("Authorization", "")
        if not raw:
            return "anonymous"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
