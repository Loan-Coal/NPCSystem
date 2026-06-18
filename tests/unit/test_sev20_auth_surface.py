"""
test_sev20_auth_surface.py - Regression tests for auth surface gaps.

Tests:
- is_public_path env-awareness (docs gating, health always open, readiness not public)
- WS per-key connection cap constant and enforcement helper

Does NOT: start HTTP/WS server or connect to Neo4j.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.auth.middleware_helpers import is_public_path
from npc_engine.api.routes.dialogue_ws import (
    MAX_WS_CONNECTIONS_PER_KEY,
    check_ws_connection_limit,
)


# ── is_public_path ────────────────────────────────────────────────────────────


def test_readiness_is_not_public_in_dev() -> None:
    """/readiness must require auth even in dev."""
    assert is_public_path("/readiness", env="dev") is False


def test_readiness_is_not_public_in_prod() -> None:
    """/readiness must require auth in prod."""
    assert is_public_path("/readiness", env="prod") is False


def test_docs_is_public_in_dev() -> None:
    """/docs is accessible without auth in dev."""
    assert is_public_path("/docs", env="dev") is True


def test_redoc_is_public_in_dev() -> None:
    """/redoc is accessible without auth in dev."""
    assert is_public_path("/redoc", env="dev") is True


def test_openapi_json_is_public_in_dev() -> None:
    """/openapi.json is accessible without auth in dev."""
    assert is_public_path("/openapi.json", env="dev") is True


def test_docs_is_not_public_in_prod() -> None:
    """/docs requires auth in prod."""
    assert is_public_path("/docs", env="prod") is False


def test_docs_is_not_public_in_staging() -> None:
    """/docs requires auth in staging."""
    assert is_public_path("/docs", env="staging") is False


def test_health_is_public_in_dev() -> None:
    """/health is always public in dev."""
    assert is_public_path("/health", env="dev") is True


def test_health_is_public_in_prod() -> None:
    """/health is always public in prod."""
    assert is_public_path("/health", env="prod") is True


def test_arbitrary_path_not_public() -> None:
    """An arbitrary API path is never public."""
    assert is_public_path("/v1/npc/dialogue", env="dev") is False


# ── WS per-key connection cap ─────────────────────────────────────────────────


def test_max_ws_connections_per_key_is_positive() -> None:
    """MAX_WS_CONNECTIONS_PER_KEY must be a positive integer."""
    assert isinstance(MAX_WS_CONNECTIONS_PER_KEY, int)
    assert MAX_WS_CONNECTIONS_PER_KEY > 0


def test_ws_connection_limit_allows_under_cap() -> None:
    """check_ws_connection_limit returns True when count is below the cap."""
    assert check_ws_connection_limit(current_count=0) is True
    assert check_ws_connection_limit(current_count=MAX_WS_CONNECTIONS_PER_KEY - 1) is True


def test_ws_connection_limit_rejects_at_cap() -> None:
    """check_ws_connection_limit returns False when count equals the cap."""
    assert check_ws_connection_limit(current_count=MAX_WS_CONNECTIONS_PER_KEY) is False


def test_ws_connection_limit_rejects_over_cap() -> None:
    """check_ws_connection_limit returns False when count exceeds the cap."""
    assert check_ws_connection_limit(current_count=MAX_WS_CONNECTIONS_PER_KEY + 10) is False


# ── WS slot enforcement (L1-01: the cap must actually be wired, not just defined) ──


@pytest.mark.asyncio
async def test_acquire_ws_slot_enforces_cap_and_releases() -> None:
    """Acquiring up to the cap succeeds; the next is rejected; releasing frees a slot."""
    from npc_engine.api.routes import dialogue_ws

    key = "test-key-hash"
    dialogue_ws._active_ws_connections.pop(key, None)
    try:
        for _ in range(MAX_WS_CONNECTIONS_PER_KEY):
            assert await dialogue_ws._acquire_ws_slot(key) is True
        # At cap: the next acquisition must be rejected.
        assert await dialogue_ws._acquire_ws_slot(key) is False
        # Releasing one slot lets exactly one more connection in.
        await dialogue_ws._release_ws_slot(key)
        assert await dialogue_ws._acquire_ws_slot(key) is True
        assert await dialogue_ws._acquire_ws_slot(key) is False
    finally:
        dialogue_ws._active_ws_connections.pop(key, None)


@pytest.mark.asyncio
async def test_release_ws_slot_cleans_up_at_zero() -> None:
    """Releasing the last slot removes the key entirely (no unbounded dict growth)."""
    from npc_engine.api.routes import dialogue_ws

    key = "test-key-cleanup"
    dialogue_ws._active_ws_connections.pop(key, None)
    assert await dialogue_ws._acquire_ws_slot(key) is True
    await dialogue_ws._release_ws_slot(key)
    assert key not in dialogue_ws._active_ws_connections
