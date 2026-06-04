"""
test_sev21_security_hardening.py - Regression tests for NEO4J_PASSWORD validator
and bounded RateLimiter bucket dict.

Does NOT: connect to Neo4j or start an HTTP server.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.config_validators import check_api_key_secret, check_neo4j_password
from npc_engine.api.rate_limit import MAX_RATE_LIMIT_BUCKETS, RateLimitMiddleware


# ── check_neo4j_password ──────────────────────────────────────────────────────


def test_check_api_key_secret_rejects_shipped_dev_secret_in_prod() -> None:
    """L1-04: the shipped dev API secret is rejected outside dev."""
    with pytest.raises(ValueError, match="API_KEY_SECRET"):
        check_api_key_secret("local_dev_secret_change_this_2026", env="prod")
    with pytest.raises(ValueError, match="API_KEY_SECRET"):
        check_api_key_secret("local_dev_secret_change_this_2026", env="staging")


def test_check_api_key_secret_allows_shipped_dev_secret_in_dev() -> None:
    """L1-04: the shipped dev secret remains usable in dev (local stack + suite)."""
    assert check_api_key_secret("local_dev_secret_change_this_2026", env="dev") == "local_dev_secret_change_this_2026"


def test_check_api_key_secret_accepts_strong_secret_in_prod() -> None:
    """A strong, non-shipped secret is accepted in prod."""
    assert check_api_key_secret("a-very-strong-unique-secret-2026", env="prod") == "a-very-strong-unique-secret-2026"


def test_check_neo4j_password_rejects_weak_in_prod() -> None:
    """The literal 'password' is rejected in prod environment."""
    with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
        check_neo4j_password("password", env="prod")


def test_check_neo4j_password_rejects_weak_in_staging() -> None:
    """The literal 'password' is rejected in staging environment."""
    with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
        check_neo4j_password("password", env="staging")


def test_check_neo4j_password_allows_weak_in_dev() -> None:
    """The literal 'password' is allowed in dev (keeps suite green)."""
    result = check_neo4j_password("password", env="dev")
    assert result == "password"


def test_check_neo4j_password_accepts_strong_in_prod() -> None:
    """A strong password is accepted in prod."""
    result = check_neo4j_password("str0ng-P@ssw0rd!xyz", env="prod")
    assert result == "str0ng-P@ssw0rd!xyz"


def test_check_neo4j_password_accepts_strong_in_dev() -> None:
    """A strong password is accepted in dev."""
    result = check_neo4j_password("str0ng-P@ssw0rd!xyz", env="dev")
    assert result == "str0ng-P@ssw0rd!xyz"


# ── RateLimiter bounded buckets ───────────────────────────────────────────────


class _FakeApp:
    """Minimal ASGI stub for RateLimitMiddleware construction."""


class _FakeSettings:
    """Minimal settings stub for RateLimitMiddleware construction."""

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_SECOND: float = 50.0
    RATE_LIMIT_BURST_SIZE: int = 100


def _make_middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=_FakeApp(), settings=_FakeSettings())


def test_max_rate_limit_buckets_constant_is_positive() -> None:
    """MAX_RATE_LIMIT_BUCKETS must be a positive integer."""
    assert isinstance(MAX_RATE_LIMIT_BUCKETS, int)
    assert MAX_RATE_LIMIT_BUCKETS > 0


def test_rate_limiter_never_exceeds_max_buckets() -> None:
    """Inserting more unique keys than the cap must not grow the dict beyond it."""
    middleware = _make_middleware()
    over_limit = MAX_RATE_LIMIT_BUCKETS + 50

    for i in range(over_limit):
        key = f"unique-key-{i}"
        middleware._ensure_bucket(key)

    assert len(middleware._buckets) <= MAX_RATE_LIMIT_BUCKETS


def test_rate_limiter_evicted_key_behaves_as_fresh_bucket() -> None:
    """After eviction, a key that was dropped should get a fresh bucket on re-insert."""
    middleware = _make_middleware()

    for i in range(MAX_RATE_LIMIT_BUCKETS):
        middleware._ensure_bucket(f"fill-key-{i}")

    middleware._ensure_bucket("new-key-after-eviction")

    assert "new-key-after-eviction" in middleware._buckets
    bucket = middleware._buckets["new-key-after-eviction"]
    assert bucket.consume() is True
